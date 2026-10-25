from datetime import datetime
import joblib
import numpy as np
import pandas as pd
import pytest
from app.services.model_service import make_pipeline, scores, predict, load_artifact, chronological_parts
from app.services.model_features import FEATURES, OrderFeatures
from app.services.explainability import global_importance, explanation_for, global_shap, EXPLANATION_VERSION
from app.models.schemas import PredictionResponse, GlobalExplanation


def population(n=500):
    rng = np.random.default_rng(8)
    X = pd.DataFrame(dict(scheduled_days=rng.integers(0, 5, n), quantity=rng.integers(1, 10, n),
        item_count=np.ones(n), net_sales=rng.uniform(10, 500, n), day_of_week=rng.integers(1, 8, n),
        month=rng.integers(1, 13, n), market=rng.choice(['Europe', 'Pacific'], n),
        region=rng.choice(['West', 'East'], n), customer_segment=['Consumer'] * n, payment_type=['DEBIT'] * n))
    y = (X.scheduled_days > 2).astype(int)
    return X, y


@pytest.fixture(params=['Logistic regression', 'Random forest'])
def explained_model(request):
    X, y = population()
    parameters = {'C': 1} if request.param == 'Logistic regression' else {'n_estimators': 40, 'max_depth': 5}
    pipeline = make_pipeline(dict(model=request.param, parameters=parameters, variant='cyclical'))
    pipeline.fit(X.iloc[:300], y.iloc[:300])
    identity = dict(model_name=request.param, model_version='test-version', dataset_fingerprint='test-data')
    pipeline.shipment_metadata_ = {**identity, 'threshold': .4, 'background': X.iloc[:24].copy(), 'explanation_version': EXPLANATION_VERSION}
    pipeline.shipment_metadata_['supported_scheduled_days'] = [0, 1, 2, 3, 4]
    explanation = global_importance(pipeline, X.iloc[300:], y.iloc[300:], identity, repeats=3)
    explanation.update(start='2017-01-01', end='2017-12-31')
    explanation['shap'] = global_shap(pipeline, X.iloc[300:340], identity)
    pipeline.shipment_metadata_['global_explanation'] = explanation
    return pipeline, explanation, X, y


def test_signal_global_names_and_local_values(explained_model):
    pipeline, explanation, X, y = explained_model
    assert explanation['features'][0]['feature'] == 'shipping_schedule'
    assert explanation['features'][0]['importance'] > .2
    assert all(r['std'] >= 0 for r in explanation['features'])
    GlobalExplanation.model_validate(explanation)
    names = pipeline.named_steps['preprocess'].get_feature_names_out()
    assert 'numeric__day_of_week_sin' in names
    assert any(name.startswith('categorical__market_') for name in names)
    assert not any('delayed' in name or 'actual_days' in name for name in names)
    values = X.iloc[310].to_dict()
    values.pop('day_of_week'); values.pop('month')
    values['order_date'] = datetime(2018, 1, 2)
    result = predict(pipeline, values)
    PredictionResponse.model_validate(result)
    assert result['threshold'] == .4
    assert result['local_explanation']['approximate'] is False
    observation = X.iloc[[310]].copy()
    observation['day_of_week'], observation['month'] = 3, 1
    local = result['local_explanation']
    total = local['base_value'] + sum(row['contribution'] for row in local['features'])
    reconstructed = total if local['output_space'] == 'probability' else 1 / (1 + np.exp(-total))
    assert reconstructed == pytest.approx(result['delay_probability'], abs=1e-5)
    assert explanation['shap']['features'][0]['feature'] == 'shipping_schedule'
    assert local['additivity_error'] < 1e-5
    assert result['recommendations']
    assert 'order_date' in values  # prediction does not mutate the caller's input
    with pytest.raises(ValueError, match='both classes'):
        global_importance(pipeline, X.iloc[:10], np.zeros(10), {})


def test_consistency_and_unavailable(explained_model, tmp_path):
    pipeline, explanation, _, _ = explained_model
    report = dict(fingerprint='test-data', model_version='test-version', global_explanation=explanation,
                  model=explanation['model_name'], threshold=.4)
    path = tmp_path / 'model.joblib'
    joblib.dump(dict(pipeline=pipeline, report=report), path)
    loaded, loaded_report = load_artifact(path, 'test-data')
    assert explanation_for(loaded) == explanation
    with pytest.raises(ValueError, match='identity mismatch'):
        load_artifact(path, 'different-data')
    pipeline.shipment_metadata_['model_version'] = 'new-version'
    with pytest.raises(ValueError, match='identity'):
        explanation_for(pipeline)
    del pipeline.shipment_metadata_
    with pytest.raises(ValueError, match='unavailable'):
        explanation_for(pipeline)


def test_calendar_basket_allowlist_and_time_boundaries():
    X, _ = population(100)
    X['actual_days'], X['delayed'] = 99, 1
    cyclical = OrderFeatures('cyclical').fit_transform(X)
    assert list(cyclical.columns) == list(OrderFeatures('cyclical').get_feature_names_out())
    angle = 2 * np.pi * (X.month - 1) / 12
    assert np.allclose(cyclical.month_sin, np.sin(angle))
    assert np.allclose(cyclical.month_sin**2 + cyclical.month_cos**2, 1)
    basket = OrderFeatures('basket').fit_transform(X)
    assert np.allclose(basket.net_per_unit, X.net_sales / X.quantity)
    assert {'actual_days', 'delayed'}.isdisjoint(basket.columns)
    X['order_date'] = pd.date_range('2017-01-01', periods=50).repeat(2)
    X['delayed'] = np.tile([0, 1], 50)
    fitting, explanation, folds = chronological_parts(X)
    for fit, validation in folds:
        assert fit.order_date.max() < validation.order_date.min()
    assert fitting.order_date.max() < explanation.order_date.min()


def test_metrics_agree_with_confusion_and_threshold():
    result = scores([0, 0, 1, 1], [.1, .7, .4, .8], .5)
    assert result['confusion_matrix'] == [[1, 1], [1, 1]]
    assert result['accuracy'] == result['precision'] == result['recall'] == result['f1'] == .5
    assert scores([0, 0, 1, 1], [.1, .7, .4, .8], .35)['recall'] == 1


def test_threshold_guard_rejects_majority_only_policy():
    from app.services.model_service import choose_threshold
    y = np.array([0] * 40 + [1] * 60)
    probability = np.array([.35] * 30 + [.65] * 10 + [.4] * 30 + [.8] * 30)
    selection = choose_threshold(y, probability)
    default, selected = selection['default_metrics'], selection['selected_metrics']
    assert selected['accuracy'] >= default['accuracy'] - .005
    assert selected['precision'] >= default['precision'] - .05
    assert selection['threshold'] > .35


def test_explanation_api_and_prediction_identity(explained_model, monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from app.services import spark_service as service
    pipeline, explanation, X, _ = explained_model
    monkeypatch.setattr(service, 'model', pipeline)
    client = TestClient(app)
    response = client.get('/api/model/explanations')
    assert response.status_code == 200 and response.json()['model_version'] == 'test-version'
    payload = X.iloc[1].to_dict()
    payload.pop('month'); payload.pop('day_of_week')
    payload.update(order_date='2018-01-01T12:00', quantity=int(payload['quantity']), item_count=int(payload['item_count']))
    prediction = client.post('/api/predict', json=payload)
    assert prediction.status_code == 200
    assert prediction.json()['local_explanation']['dataset_fingerprint'] == response.json()['dataset_fingerprint']
    for days in range(8):
        response = client.post('/api/predict', json={**payload, 'scheduled_days': days})
        assert response.status_code == 200
        assert ('not observed' in response.json()['scope']) == (days not in pipeline.shipment_metadata_['supported_scheduled_days'])
    assert client.post('/api/predict', json={**payload, 'scheduled_days': 10}).status_code == 422
    assert client.post('/api/predict', json={**payload, 'scheduled_days': -1}).status_code == 422
    assert client.post('/api/predict', json={**payload, 'scheduled_days': 2.5}).status_code == 422
    pipeline.shipment_metadata_['model_version'] = 'new-version'
    assert client.get('/api/model/explanations').status_code == 503
    assert client.post('/api/predict', json=payload).status_code == 503


def test_final_test_supplier_opens_only_after_explanation(monkeypatch):
    from app.services import model_service as model
    X, y = population(100)
    X['order_date'], X['delayed'] = pd.date_range('2017-01-01', periods=100), y
    fitting, validation = X.iloc[:60], X.iloc[60:80]
    pipeline = make_pipeline(dict(model='Logistic regression', variant='numeric', parameters={'C': 1}))
    pipeline.fit(fitting[FEATURES], fitting.delayed)
    monkeypatch.setattr(model, 'select_model', lambda training, progress: (
        pipeline, 'Logistic regression', {'threshold_selection': {'threshold': .5}}, fitting, validation))
    seen = []
    def supplier():
        assert hasattr(pipeline, 'shipment_metadata_')
        assert pipeline.shipment_metadata_['global_explanation']['rows'] == 20
        seen.append(True)
        return X.iloc[80:]
    _, report = model.fit_evaluate(X.iloc[:80], supplier, 'no-test-leak')
    assert seen == [True] and report['test_rows'] == 20
