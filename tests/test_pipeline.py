import pytest
from app.services.data_pipeline import process
from app.services import spark_service as service


def test_order_grain_duplicates_missing_and_cancelled(raw_factory, monkeypatch):
    raw = raw_factory([{}, {}, {'Order Item Id':'2','Market':''},
        {'Order Id':'2','Order Item Id':'3','Delivery Status':'Shipping canceled','Order Status':'SUSPECTED_FRAUD','Late_delivery_risk':'0'},
        {'Order Id':'3','Order Item Id':'4','Days for shipping (real)':'2','Late_delivery_risk':'0','Delivery Status':'Advance shipping'}])
    df, q = process(raw)
    assert q['raw_rows'] == 5 and q['exact_duplicate_rows'] == 1
    assert q['cancelled_orders'] == 1 and q['eligible_orders'] == 2
    first = df.filter('order_id = 1').first()
    assert first.quantity == 2 and first.net_sales == 180 and first.market == 'Europe'
    monkeypatch.setattr(service, 'global_df_clean', df)
    df.createOrReplaceTempView('shipments')
    result = service.analytics()
    assert result['overview']['total_orders'] == 2
    assert result['overview']['delay_rate'] == .5
    assert sum(r['total_orders'] for r in result['views']['temporal']) == 2
    assert sum(c['total_orders'] for c in result['heatmap']) == 2
    assert sum(c['delayed_orders'] for c in result['heatmap']) == 1
    assert result['heatmap'][0]['delay_rate'] == .5
    filtered = service.analytics(shipping_mode='Standard Class')
    assert sum(c['total_orders'] for c in filtered['heatmap']) == filtered['overview']['total_orders']
    empty_result = service.analytics(region='not a region')
    assert empty_result['heatmap'] == []
    empty = empty_result['overview']
    assert empty['total_orders'] == 0 and empty['delay_rate'] is None
    # Changing filters must not evict the shared order cache or alter the source view.
    assert service.global_spark.catalog.isCached('shipments')
    assert service.analytics()['overview']['total_orders'] == 2
    df.unpersist()


def test_invalid_line_excludes_whole_order_and_conflicting_items(raw_factory):
    raw = raw_factory([{}, {'Order Item Id':'2','Sales':'broken'},
        {'Order Id':'2','Order Item Id':'3'}, {'Order Id':'2','Order Item Id':'3','Sales':'200'},
        {'Order Id':'3','Order Item Id':'4','order date (DateOrders)':'bad date'},
        {'Order Id':'4','Order Item Id':'5'}])
    df, q = process(raw)
    assert q['invalid_rows'] == 2 and q['invalid_order_dates'] == 1
    assert q['conflicting_item_ids'] == 1 and q['eligible_orders'] == 1
    assert df.first().order_id == 4
    df.unpersist()


def test_conflicting_order_dimensions_and_target(raw_factory):
    raw = raw_factory([{}, {'Order Item Id':'2','Market':'LATAM'},
        {'Order Id':'2','Order Item Id':'3','Late_delivery_risk':'0'},
        {'Order Id':'3','Order Item Id':'4','Market':''}])
    df, q = process(raw)
    assert q['inconsistent_orders'] == 1 and q['target_mismatch_orders'] == 1
    assert df.first().market == 'Unknown'
    df.unpersist()


def test_empty_dataset(raw_factory):
    with pytest.raises(ValueError, match='empty'):
        process(raw_factory([]))
