from datetime import datetime, timedelta
import pytest
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
    selection = report['selection']
    for fold in selection['folds']:
        assert fold['fit_end'] < fold['validation_start']
    assert selection['validation_end'] < report['test_start']
    comparison = selection['comparison']
    assert {row['model'] for row in comparison} == {'Logistic regression', 'Random forest'}
    selected = [row for row in comparison if row['selected']]
    assert len(selected) == 1 and selected[0]['model'] == report['model']
    assert selected[0]['mean_roc_auc'] == max(row['mean_roc_auc'] for row in comparison)
    assert report['train_end'] < report['global_explanation']['start']
    assert report['global_explanation']['end'] < report['test_start']
    assert len(selection['trials']) == 8
    assert report['threshold'] == selection['threshold_selection']['threshold']
    assert report['train_end'] < report['test_start']
    assert report['train_rows'] + report['test_rows'] <= 100
    assert sum(map(sum, report['confusion_matrix'])) == report['test_rows']
    assert set(FEATURES).isdisjoint({'actual_days','delivery_status','delayed','order_status','shipping_mode'})
    loaded, loaded_report = train_or_load(df)
    assert loaded_report['state'] == 'loaded'
    assert loaded_report['selection'] == selection
    assert loaded_report['global_explanation'] == report['global_explanation']
    values = {'order_date':datetime(2018,1,1),'scheduled_days':4,'quantity':1,'net_sales':90,
        'item_count':1,'market':'unseen market','region':'Western Europe','shipping_mode':'Standard Class',
        'customer_segment':'Consumer','payment_type':'DEBIT'}
    a, b = predict(pipeline, values.copy()), predict(loaded, values.copy())
    assert a['delay_probability'] == pytest.approx(b['delay_probability'])
    assert 0 <= a['delay_probability'] <= 1
    assert a['model_version'] == b['model_version']
    for row in a['local_explanation']['features']:
        loaded_row = next(r for r in b['local_explanation']['features'] if r['feature'] == row['feature'])
        assert row['contribution'] == pytest.approx(loaded_row['contribution'], abs=1e-12)
    assert a['local_explanation']['model_version'] == report['model_version']
    assert a['predicted_delayed'] == (a['delay_probability'] >= report['threshold'])
    # Forced retraining replaces the explanation identity, even for identical data.
    refreshed, fresh_report = train_or_load(df, force=True)
    assert fresh_report['model_version'] != report['model_version']
    assert fresh_report['global_explanation']['model_version'] == fresh_report['model_version']
    assert predict(refreshed, values.copy())['model_version'] == fresh_report['model_version']
    assert load_report_consistent(df, fresh_report)
    df.unpersist()


def load_report_consistent(df, report):
    _, loaded = train_or_load(df)
    return loaded['model_version'] == report['model_version']
