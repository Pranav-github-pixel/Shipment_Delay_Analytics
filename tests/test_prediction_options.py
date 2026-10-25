import pytest
from app.services import spark_service as service
from app.services.data_pipeline import process


def test_observed_options_and_price_paging(raw_factory, monkeypatch):
    df, _ = process(raw_factory([
        {'Order Id': '1', 'Order Item Id': '1', 'Market': 'Europe', 'Order Region': 'West', 'Order Item Total': '90'},
        {'Order Id': '2', 'Order Item Id': '2', 'Market': 'Pacific', 'Order Region': 'East', 'Order Item Total': '120'},
        {'Order Id': '3', 'Order Item Id': '3', 'Market': 'Europe', 'Order Region': 'West', 'Order Item Total': '90'}]))
    monkeypatch.setattr(service, 'global_df_clean', df)
    monkeypatch.setattr(service, 'model_report', {'model_version': 'catalog-version'})
    first = service.prediction_options(0, page_size=1)
    second = service.prediction_options(1, page_size=1)
    assert first['net_sales'] == [90] and second['net_sales'] == [120]
    assert first['price_count'] == 2 and first['model_version'] == 'catalog-version'
    assert first['regions_by_market'] == {'Europe': ['West'], 'Pacific': ['East']}
    assert first['scheduled_days'] == list(range(8))
    assert first['observed_scheduled_days'] == [4]
    with pytest.raises(ValueError, match='out of range'):
        service.prediction_options(2, page_size=1)
    df.unpersist()
