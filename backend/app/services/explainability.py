"""Cached SHAP explanations plus held-out grouped permutation diagnostics."""
from functools import lru_cache
from threading import RLock
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from app.services.model_features import FEATURES, GROUPS

EXPLANATION_VERSION = 'shap-v1'
LIMITATION = ('SHAP explains this fitted model relative to a training reference, not causes or guaranteed interventions. '
              'Correlated inputs can share attribution. Encoded categories are summed into original input groups.')


def global_importance(pipeline, observations, labels, identity, repeats=5):
    if len(np.unique(labels)) != 2:
        raise ValueError('Global ROC-AUC importance requires both classes in explanation validation')
    X = observations[FEATURES].copy().reset_index(drop=True)
    y = np.asarray(labels)
    baseline = float(roc_auc_score(y, pipeline.predict_proba(X)[:, 1]))
    rng = np.random.default_rng(42)
    rows = []
    for group, (label, columns) in GROUPS.items():
        decreases = []
        for _ in range(repeats):
            shuffled = X.copy()
            shuffled[columns] = X.iloc[rng.permutation(len(X))][columns].to_numpy()
            decreases.append(baseline - roc_auc_score(y, pipeline.predict_proba(shuffled)[:, 1]))
        rows.append(dict(feature=group, label=label, columns=columns,
                         importance=float(np.mean(decreases)), std=float(np.std(decreases))))
    return {**identity, 'method': 'Grouped permutation importance', 'metric': 'ROC-AUC decrease',
            'scope': 'Dedicated chronological explanation-validation block; excluded from fitting, tuning and final test',
            'grouping': 'Original input groups permuted before engineering and one-hot encoding',
            'rows': len(X), 'repeats': repeats, 'baseline_score': baseline,
            'limitations': LIMITATION, 'features': sorted(rows, key=lambda r: r['importance'], reverse=True)}


def dense(matrix):
    return matrix.toarray() if hasattr(matrix, 'toarray') else np.asarray(matrix)


def encoded_groups(pipeline):
    preprocess = pipeline.named_steps['preprocess']
    names = preprocess.get_feature_names_out().tolist()
    groups = {group: [] for group in GROUPS}
    source_group = {column: group for group, (_, columns) in GROUPS.items() for column in columns}
    source_group.update(day_of_week_sin='weekday', day_of_week_cos='weekday', month_sin='month', month_cos='month',
                        net_per_unit='order_value', net_per_line='order_value', units_per_line='basket_size')
    numeric_columns = preprocess.transformers_[0][2]
    for i, column in enumerate(numeric_columns):
        groups[source_group[column]].append(i)
    offset = len(numeric_columns)
    encoder = preprocess.named_transformers_['categorical']
    for column, categories in zip(preprocess.transformers_[1][2], encoder.categories_):
        groups[source_group[column]].extend(range(offset, offset + len(categories)))
        offset += len(categories)
    if sorted(i for indices in groups.values() for i in indices) != list(range(len(names))):
        raise ValueError('SHAP feature mapping does not cover the fitted preprocessing outputs')
    return names, groups


@lru_cache(maxsize=4)
def shap_context(pipeline, model_version):
    import shap
    metadata = pipeline.shipment_metadata_
    background = metadata.get('background')
    if not isinstance(background, pd.DataFrame) or background.empty:
        raise ValueError('SHAP training reference unavailable. Reprocess the dataset')
    background = background.iloc[:32][FEATURES]
    transformed = dense(pipeline[:-1].transform(background))
    classifier = pipeline.named_steps['classifier']
    if hasattr(classifier, 'estimators_') or hasattr(classifier, 'tree_'):
        explainer = shap.TreeExplainer(classifier, data=transformed, feature_perturbation='interventional', model_output='probability')
        output_space = 'probability'
    else:
        explainer = shap.LinearExplainer(classifier, transformed)
        output_space = 'log_odds'
    return explainer, output_space, encoded_groups(pipeline), len(background), RLock()


def shap_values(pipeline, observations):
    metadata = pipeline.shipment_metadata_
    explainer, space, (names, groups), background_rows, lock = shap_context(pipeline, metadata['model_version'])
    transformed = dense(pipeline[:-1].transform(observations[FEATURES]))
    with lock:
        explanation = explainer(transformed)
    values = np.asarray(explanation.values)
    bases = np.asarray(explanation.base_values)
    if values.ndim == 3:
        values, bases = values[:, :, 1], bases[:, 1]
    bases = np.broadcast_to(bases, (len(observations),))
    grouped = {group: values[:, indices].sum(axis=1) for group, indices in groups.items()}
    total = bases + values.sum(axis=1)
    reconstructed = total if space == 'probability' else 1 / (1 + np.exp(-np.clip(total, -700, 700)))
    actual = pipeline.predict_proba(observations[FEATURES])[:, 1]
    errors = np.abs(actual - reconstructed)
    if not np.allclose(actual, reconstructed, atol=1e-5, rtol=1e-5):
        raise ValueError('SHAP additivity check failed for the active model')
    return grouped, bases, space, background_rows, errors, names


def global_shap(pipeline, observations, identity):
    X = observations[FEATURES]
    grouped, bases, space, reference_rows, errors, names = shap_values(pipeline, X)
    rows = [dict(feature=group, label=GROUPS[group][0], columns=GROUPS[group][1],
                 importance=float(np.abs(values).mean()), signed_mean=float(values.mean()), std=float(values.std()))
            for group, values in grouped.items()]
    return {**identity, 'method': 'Tree SHAP' if space == 'probability' else 'Linear SHAP',
            'metric': 'Mean absolute grouped SHAP value', 'output_space': space,
            'scope': 'Dedicated chronological explanation-validation observations; never final test',
            'rows': len(X), 'reference_rows': reference_rows, 'base_value': float(bases.mean()),
            'max_additivity_error': float(errors.max()), 'encoded_feature_names': names,
            'variation': 'Standard deviation of signed group contributions across explained orders, not repeat uncertainty',
            'limitations': LIMITATION, 'features': sorted(rows, key=lambda r: r['importance'], reverse=True)}


def explanation_for(pipeline, allow_legacy=False):
    metadata = getattr(pipeline, 'shipment_metadata_', None)
    if not metadata or not metadata.get('global_explanation'):
        raise ValueError('Explanation unavailable. Process a dataset first')
    report = metadata['global_explanation']
    reports = [report] + ([report['shap']] if 'shap' in report else [])
    if any(r[k] != metadata[k] for r in reports for k in ('model_name', 'model_version', 'dataset_fingerprint')):
        raise ValueError('Explanation identity does not match the active model')
    if not allow_legacy and ('shap' not in report or metadata.get('explanation_version') != EXPLANATION_VERSION):
        raise ValueError('SHAP explanation unavailable. Reprocess the dataset to refresh the artifact')
    return report


def local_explanation(pipeline, observation):
    explanation_for(pipeline)
    metadata = pipeline.shipment_metadata_
    grouped, bases, space, reference_rows, errors, _ = shap_values(pipeline, observation)
    rows = []
    for group, values in grouped.items():
        label, columns = GROUPS[group]
        rows.append(dict(feature=group, label=label, columns=columns, contribution=float(values[0]),
            observed_values={c: observation.iloc[0][c].item() if isinstance(observation.iloc[0][c], np.generic)
                             else observation.iloc[0][c] for c in columns}))
    probability = float(pipeline.predict_proba(observation)[0, 1])
    return {k: metadata[k] for k in ('model_name', 'model_version', 'dataset_fingerprint')} | {
        'method': 'Tree SHAP' if space == 'probability' else 'Linear SHAP', 'approximate': False,
        'scope': f'SHAP relative to {reference_rows} deterministic training-reference orders',
        'output_space': space, 'base_value': float(bases[0]), 'output_probability': probability,
        'additivity_error': float(errors[0]), 'reference_rows': reference_rows,
        'interpretation': ('Positive SHAP values increase model risk; negative values decrease it. '
                          'Base value plus all contributions reconstructs the model output in the stated space. '
                          'For log_odds, apply the logistic function to recover probability.'),
        'limitations': LIMITATION, 'features': sorted(rows, key=lambda r: abs(r['contribution']), reverse=True)}
