"""Operator-facing, deterministic rules; these are not causal interventions."""
RULES = {
    'shipping_schedule': ('dispatch_readiness', 'Check dispatch readiness',
        'Confirm stock allocation, pick-and-pack readiness and the carrier cutoff for the selected service. Review promise feasibility; do not extend it simply to change this score.'),
    'destination': ('route_review', 'Review the destination route',
        'Check current carrier coverage and known route exceptions for this destination; arrange proactive tracking if warranted.'),
    'basket_size': ('capacity_review', 'Review fulfilment capacity',
        'Confirm that all item lines are available and packing capacity can meet the dispatch cutoff.'),
    'order_value': ('handling_review', 'Verify handling requirements',
        'Review packaging, documentation and required checks for this order. Order value is a model association, not proof of extra processing.'),
    'weekday': ('cutoff_review', 'Check the operating calendar',
        'Verify working-day cutoffs and staffing coverage for this order date.'),
    'month': ('season_review', 'Review current capacity',
        'Check current fulfilment capacity and scheduled closures; a calendar association does not establish a seasonal cause.'),
}


def recommend(probability, threshold, explanation):
    if probability < threshold:
        return [{'rule_id': 'routine_monitoring', 'title': 'Continue routine fulfilment',
                 'action': 'Follow normal dispatch checks and tracking. A below-threshold score does not guarantee on-time delivery.',
                 'trigger': 'Predicted on time at the selected threshold', 'feature': None, 'shap_value': None}]
    rows = []
    for feature in explanation['features']:
        group = feature['feature']
        if feature['contribution'] <= 1e-6 or group not in RULES:
            continue
        code, title, action = RULES[group]
        rows.append({'rule_id': code, 'title': title, 'action': action, 'feature': group,
                     'shap_value': feature['contribution'],
                     'trigger': f"Predicted late; {feature['label']} has a positive SHAP contribution in {explanation['output_space']}"})
        if len(rows) == 3:
            break
    return rows or [{'rule_id': 'operator_review', 'title': 'Review this flagged order',
        'action': 'Verify fulfilment readiness and tracking. The strongest model factors do not identify a supported operational intervention.',
        'trigger': 'Predicted late without an actionable positive SHAP factor', 'feature': None, 'shap_value': None}]
