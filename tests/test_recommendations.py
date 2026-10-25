from app.services.recommendations import recommend


def test_rules_use_prediction_and_positive_actionable_shap():
    explanation = {'output_space': 'probability', 'features': [
        {'feature': 'payment_type', 'label': 'Payment type', 'contribution': .2},
        {'feature': 'shipping_schedule', 'label': 'Scheduled days', 'contribution': .1},
        {'feature': 'destination', 'label': 'Destination', 'contribution': -.1}]}
    rows = recommend(.8, .5, explanation)
    assert [r['rule_id'] for r in rows] == ['dispatch_readiness']
    assert rows[0]['shap_value'] == .1
    assert recommend(.3, .5, explanation)[0]['rule_id'] == 'routine_monitoring'
    assert recommend(.8, .5, {'output_space': 'probability', 'features': []})[0]['rule_id'] == 'operator_review'
