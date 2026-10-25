from fastapi.testclient import TestClient
from main import app
from app.services import spark_service as service

client = TestClient(app)


def test_api_unavailable_and_validation(monkeypatch):
    monkeypatch.setattr(service, 'model', None)
    monkeypatch.setattr(service, 'global_df_clean', None)
    monkeypatch.setattr(service, 'quality', None)
    monkeypatch.setattr(service, 'job', {'state':'idle','stage':'Ready'})
    assert client.get('/api/status').status_code == 200
    assert client.get('/api/model/explanations').status_code == 503
    assert client.get('/api/analytics').status_code == 409
    assert client.get('/api/analytics?start=2020-01-01&end=2019-01-01').status_code == 422
    assert client.post('/api/query', json={'query':''}).status_code == 422
    assert client.post('/api/query', json={'query':'DROP TABLE shipments'}).status_code == 400
    payload = {'order_date':'2018-01-01T12:00','scheduled_days':4,'quantity':1,'net_sales':90,
               'item_count':1,'market':'Europe','region':'Western Europe',
               'customer_segment':'Consumer','payment_type':'DEBIT'}
    assert client.post('/api/predict', json=payload).status_code == 503
    assert client.post('/api/predict', json={**payload,'actual_days':5}).status_code == 422
    assert client.post('/api/predict', json={**payload,'quantity':0}).status_code == 422


def test_concurrent_job_rejected(monkeypatch):
    monkeypatch.setattr(service, 'job', {'state':'running','stage':'Processing'})
    assert client.post('/api/ingest').status_code == 409
    assert client.get('/api/analytics').status_code == 409
