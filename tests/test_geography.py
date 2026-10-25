from collections import OrderedDict
from datetime import date
from xml.etree import ElementTree as ET
import pytest
from fastapi.testclient import TestClient
from app.services import geography as geo, spark_service as service
from app.services.data_pipeline import process
from main import app


def test_aliases_merging_and_map_counts():
    data = geo.mapped_data([
        dict(country='España', total_orders=10, delayed_orders=4),
        dict(country='Spain', total_orders=5, delayed_orders=2),
        dict(country='Estados Unidos', total_orders=10, delayed_orders=3),
        dict(country='Missing country', total_orders=2, delayed_orders=1)])
    assert data['total_orders'] == 27 and data['delayed_orders'] == 10
    assert data['unmapped_orders'] == 2 and data['unmapped_delayed_orders'] == 1
    spain = next(r for r in data['countries'] if r['country'] == 'Spain')
    assert spain['total_orders'] == 15 and spain['delayed_orders'] == 6 and spain['delay_rate'] == .4
    assert len(spain['source_labels']) == 2
    for label in ['Guayana Francesa', 'Guadalupe', 'Martinica', 'Hong Kong', 'Baréin', 'Singapur',
                  'Arabia Saudí', 'Myanmar (Birmania)', 'Suazilandia', 'Macedonia', 'República de Gambia']:
        assert geo.resolve_country(label), label
    assert sum(r['delayed_orders'] for r in data['countries']) + data['unmapped_delayed_orders'] == data['delayed_orders']
    with pytest.raises(ValueError):
        geo.mapped_data([dict(country='España', total_orders=1, delayed_orders=2)])


def test_svg_real_boundaries_reference_points_and_safe_content():
    data = geo.mapped_data([dict(country='España', total_orders=5, delayed_orders=4)])
    data['countries'][0]['source_labels'] = ['</title><script>alert(1)</script>']
    svg = geo.render_map(data)
    root = ET.fromstring(svg)
    ns = {'s': geo.NS}
    assert len(root.findall('.//s:path', ns)) > 150
    assert root.find('.//s:script', ns) is None
    assert '&lt;script&gt;' in svg
    point = root.findall('.//s:circle', ns)[0]
    assert float(point.attrib['r']) == 30
    assert 'Spain' in point.find('s:title', ns).text
    assert 'small sample' in point.find('s:title', ns).text
    assert 'not exact shipment coordinates' in root.find('s:desc', ns).text
    empty = ET.fromstring(geo.render_map(geo.mapped_data([])))
    assert len(empty.findall('.//s:path', ns)) > 150
    assert 'nan' not in svg.lower() and 'Infinity' not in svg


def test_order_country_metadata_filters_and_versioned_cache(raw_factory, monkeypatch):
    raw = raw_factory([
        {'Order Id':'1', 'Order Item Id':'1'},
        {'Order Id':'1', 'Order Item Id':'2'},
        {'Order Id':'2', 'Order Item Id':'3'},
        {'Order Id':'2', 'Order Item Id':'4', 'Order Country':'Francia'},
        {'Order Id':'3', 'Order Item Id':'5', 'Delivery Status':'Shipping canceled', 'Order Status':'CANCELED', 'Late_delivery_risk':'0'},
        {'Order Id':'4', 'Order Item Id':'6', 'Order Country':'', 'Days for shipping (real)':'2', 'Late_delivery_risk':'0', 'Delivery Status':'Advance shipping'}])
    eligible, _ = process(raw)
    frame = geo.prepare_orders(raw, eligible).cache()
    assert frame.count() == eligible.count() == 3
    assert 'destination_country' not in eligible.columns
    assert frame.filter('order_id = 1').first().destination_country == 'España'
    assert frame.filter('order_id = 2').first().destination_country == 'Unknown'
    monkeypatch.setattr(service, 'global_df_clean', eligible)
    monkeypatch.setattr(service, 'global_geographic_df', frame)
    monkeypatch.setattr(service, 'geographic_cache', OrderedDict())
    monkeypatch.setattr(service, 'job', dict(id='geography-v1', state='completed', stage='Dataset ready'))
    result = service.geographic_map()
    assert result['total_orders'] == 3 and result['delayed_orders'] == 2
    assert result['countries'][0]['total_orders'] == 1 and result['unmapped_orders'] == 2
    assert service.geographic_map() is result
    assert service.geographic_map(region='Western Europe')['total_orders'] == 3
    assert service.geographic_map(shipping_mode='First Class')['total_orders'] == 0
    assert service.geographic_map(start=date(2018, 1, 1))['total_orders'] == 0
    assert service.geographic_map(end=date(2016, 12, 31))['total_orders'] == 0
    client = TestClient(app)
    api_result = client.get('/api/analytics/map')
    assert api_result.status_code == 200
    assert api_result.json()['total_orders'] == result['total_orders']
    monkeypatch.setattr(service, 'job', dict(id='geography-v2', state='completed', stage='Dataset ready'))
    assert service.geographic_map()['dataset_job_id'] == 'geography-v2'
    assert service.geographic_map() is not result
    missing = geo.prepare_orders(raw.drop('Order Country'), eligible)
    assert {r.destination_country for r in missing.select('destination_country').distinct().collect()} == {'Unknown'}
    frame.unpersist(); eligible.unpersist()


def test_map_unavailable_and_bad_dates(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(service, 'job', dict(state='idle', stage='Ready'))
    monkeypatch.setattr(service, 'global_df_clean', None)
    assert client.get('/api/analytics/map').status_code == 409
    assert client.get('/api/analytics/map?start=2020-01-01&end=2019-01-01').status_code == 422
    monkeypatch.setattr(service, 'job', dict(state='running', stage='Processing'))
    assert client.get('/api/analytics/map').status_code == 409
