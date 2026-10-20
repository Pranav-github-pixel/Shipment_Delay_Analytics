from datetime import datetime, timedelta
from app.services.data_pipeline import process
from app.services.model_service import train_or_load, predict, FEATURES
from app import config


def test_chronological_training_loading_and_prediction(raw_factory, monkeypatch, tmp_path):
    rows = []
    for i in range(120):
        dt = datetime(2017,1,1) + timedelta(days=i)
        rows.append({'Order Id':str(i+1),'Order Item Id':str(i+1),
            'order date (DateOrders)':dt.strftime('%m/%d/%Y %H:%M'),
            'Late_delivery_risk':str(i%2), 'Days for shipping (real)':str(5 if i%2 else 2),
            'Delivery Status':'Late delivery' if i%2 else 'Advance shipping'})
    df, _ = process(raw_factory(rows))
    monkeypatch.setattr(config, 'ARTIFACT_DIR', tmp_path)
    monkeypatch.setattr(config, 'MODEL_MAX_ROWS', 100)
    pipeline, report = train_or_load(df)
    assert report['state'] == 'trained'
    assert report['train_end'] < report['test_start']
    assert report['train_rows'] + report['test_rows'] <= 100
    assert sum(map(sum, report['confusion_matrix'])) == report['test_rows']
    assert set(FEATURES).isdisjoint({'actual_days','delivery_status','delayed','order_status','shipping_mode'})
    loaded, loaded_report = train_or_load(df)
    assert loaded_report['state'] == 'loaded'
    values = {'order_date':datetime(2018,1,1),'scheduled_days':4,'quantity':1,'net_sales':90,
        'item_count':1,'market':'unseen market','region':'Western Europe','shipping_mode':'Standard Class',
        'customer_segment':'Consumer','payment_type':'DEBIT'}
    a, b = predict(pipeline, values.copy()), predict(loaded, values.copy())
    assert a == b and 0 <= a['delay_probability'] <= 1
    df.unpersist()
