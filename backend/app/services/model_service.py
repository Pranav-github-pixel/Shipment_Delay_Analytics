import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
from copy import deepcopy
import joblib
import numpy as np
import pandas as pd
import sklearn
from pyspark.sql import functions as F
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
from app import config
from app.services.model_features import FEATURES, NUMERIC, CATEGORICAL, OrderFeatures, numeric_features
from app.services.explainability import global_importance, local_explanation, explanation_for, global_shap, EXPLANATION_VERSION
from app.services.recommendations import recommend


class PredictionInputError(ValueError):
    pass


def scores(y, probability, threshold=.5):
    pred = np.asarray(probability) >= threshold
    return dict(accuracy=float(accuracy_score(y, pred)), precision=float(precision_score(y, pred, zero_division=0)),
                recall=float(recall_score(y, pred, zero_division=0)), f1=float(f1_score(y, pred, zero_division=0)),
                roc_auc=float(roc_auc_score(y, probability)), confusion_matrix=confusion_matrix(y, pred, labels=[0, 1]).tolist(),
                delay_rate=float(np.mean(y)), majority_baseline_accuracy=float(max(np.mean(y), 1 - np.mean(y))))


def choose_threshold(y, probability):
    default = scores(y, probability)
    trials = [(round(float(t), 3), scores(y, probability, t)) for t in np.arange(.25, .751, .025)]
    eligible = [(t, m) for t, m in trials if m['accuracy'] >= default['accuracy'] - .005
                and m['precision'] >= default['precision'] - .05]
    threshold, tuned = max(eligible + [(.5, default)], key=lambda p: (p[1]['f1'], -abs(p[0] - .5)))
    if tuned['f1'] < default['f1'] + .005:
        threshold, tuned = .5, default
    return dict(threshold=threshold,
                metric='Validation F1 gain >=0.005, with accuracy loss <=0.005 and precision loss <=0.05 versus 0.5; otherwise retain 0.5',
                default_metrics=default, selected_metrics=tuned,
                trials=[dict(threshold=t, metrics=m) for t, m in trials])


def make_pipeline(spec):
    logistic = spec['model'] == 'Logistic regression'
    classifier = (LogisticRegression(max_iter=1500, random_state=42, **spec['parameters']) if logistic else
                  RandomForestClassifier(random_state=42, n_jobs=2, **spec['parameters']))
    preprocess = ColumnTransformer([('numeric', StandardScaler() if logistic else 'passthrough', numeric_features(spec['variant'])),
                                   ('categorical', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL)])
    return Pipeline([('features', OrderFeatures(spec['variant'])), ('preprocess', preprocess), ('classifier', classifier)])


def chronological_parts(training):
    ordered = training.sort_values('order_date').reset_index(drop=True)
    dates = ordered.order_date
    cuts = [dates.iloc[int(len(dates) * f)] for f in (.45, .65, .85)]
    folds = [(ordered[dates < cuts[0]], ordered[(dates >= cuts[0]) & (dates < cuts[1])]),
             (ordered[dates < cuts[1]], ordered[(dates >= cuts[1]) & (dates < cuts[2])])]
    explanation = ordered[dates >= cuts[2]]
    for part in [p for fold in folds for p in fold] + [explanation]:
        if len(part) < 5 or part.delayed.nunique() != 2:
            raise ValueError('Chronological fit, validation and explanation blocks require five orders and both classes each')
    return ordered[dates < cuts[2]], explanation, folds


def select_model(training, progress=None):
    fitting, explanation, folds = chronological_parts(training)
    rf = dict(n_estimators=200, max_depth=16, min_samples_leaf=5, max_features='sqrt')
    specs = [dict(model='Logistic regression', variant='numeric', parameters={'C': c}, baseline=c == 1) for c in (1, .1)]
    specs += [dict(model='Random forest', variant='numeric', parameters=rf, baseline=True),
              dict(model='Random forest', variant='numeric', parameters={**rf, 'max_depth': 10, 'min_samples_leaf': 20}, baseline=False)]
    trials, probabilities = [], {}
    y_validation = np.concatenate([v.delayed.to_numpy(dtype=int) for _, v in folds])

    def evaluate(spec):
        if progress:
            progress(stage=f"Validating {spec['model']} / {spec['variant']} (trial {len(trials) + 1}/8)")
        fold_scores, predictions = [], []
        for fit, validation in folds:
            pipeline = make_pipeline(spec)
            pipeline.fit(fit[FEATURES], fit.delayed.astype(int))
            probability = pipeline.predict_proba(validation[FEATURES])[:, 1]
            fold_scores.append(scores(validation.delayed.astype(int), probability))
            predictions.append(probability)
        trial_id = f'trial-{len(trials) + 1}'
        probability = np.concatenate(predictions)
        row = {**spec, 'id': trial_id, 'fold_metrics': fold_scores,
               'mean_roc_auc': float(np.mean([s['roc_auc'] for s in fold_scores])),
               'metrics': scores(y_validation, probability), 'selected': False, 'eligible': True}
        trials.append(row)
        probabilities[trial_id] = probability
        return row

    for spec in specs:
        evaluate(spec)
    for family in ('Logistic regression', 'Random forest'):
        base = max([r for r in trials if r['model'] == family], key=lambda r: r['mean_roc_auc'])
        for variant in ('cyclical', 'basket'):
            row = evaluate(dict(model=family, variant=variant, parameters=base['parameters'], baseline=False))
            row['eligible'] = row['mean_roc_auc'] >= base['mean_roc_auc'] + .002 and all(
                a['roc_auc'] >= b['roc_auc'] - .01 for a, b in zip(row['fold_metrics'], base['fold_metrics']))
            row['retention_reason'] = 'Stable validation benefit' if row['eligible'] else 'Rejected: no stable >=0.002 mean AUC gain'
    winner = max([r for r in trials if r['eligible']], key=lambda r: r['mean_roc_auc'])
    winner['selected'] = True
    probability = probabilities[winner['id']]
    threshold_selection = choose_threshold(y_validation, probability)
    comparison = []
    for family in ('Logistic regression', 'Random forest'):
        best = max([r for r in trials if r['model'] == family and r['eligible']], key=lambda r: r['mean_roc_auc'])
        comparison.append({k: best[k] for k in ('model', 'variant', 'parameters', 'mean_roc_auc', 'metrics', 'selected')})
    fold_info = [dict(fit_rows=len(a), validation_rows=len(b), fit_start=str(a.order_date.min()), fit_end=str(a.order_date.max()),
                      validation_start=str(b.order_date.min()), validation_end=str(b.order_date.max())) for a, b in folds]
    selection = dict(criterion='Highest mean ROC-AUC across two expanding chronological folds; stable feature benefit required',
                     fit_rows=len(fitting), validation_rows=len(y_validation), folds=fold_info, fit_end=str(fitting.order_date.max()),
                     validation_start=fold_info[0]['validation_start'], validation_end=fold_info[-1]['validation_end'],
                     comparison=comparison, trials=trials, best_parameters=winner['parameters'], feature_variant=winner['variant'],
                     threshold_selection=threshold_selection,
                     baseline_comparison=[r for r in trials if r['baseline']])
    pipeline = make_pipeline(winner)
    pipeline.fit(fitting[FEATURES], fitting.delayed.astype(int))
    return pipeline, winner['model'], selection, fitting, explanation


def fingerprint(df):
    digest = F.sha2(F.to_json(F.struct(*[F.col(c) for c in sorted(df.columns)])), 256)
    stats = df.select(digest.alias('h')).agg(F.count('*').alias('n'), F.min('h').alias('min'), F.max('h').alias('max'),
        F.sum(F.conv(F.substring('h', 1, 15), 16, 10).cast('decimal(38,0)')).alias('sum1'),
        F.sum(F.conv(F.substring('h', 16, 15), 16, 10).cast('decimal(38,0)')).alias('sum2')).first().asDict()
    return hashlib.sha256(json.dumps([stats, config.PIPELINE_VERSION, config.MODEL_MAX_ROWS, sklearn.__version__], sort_keys=True, default=str).encode()).hexdigest()


def load_artifact(path, key):
    artifact = joblib.load(path)  # Trusted, application-owned files only.
    pipeline, report = artifact['pipeline'], artifact['report']
    explanation = explanation_for(pipeline, allow_legacy=True)
    if (report['fingerprint'] != key or explanation['dataset_fingerprint'] != key
            or report['model_version'] != explanation['model_version'] or report['global_explanation'] != explanation
            or report['model'] != explanation['model_name'] or report['threshold'] != pipeline.shipment_metadata_['threshold']):
        raise ValueError('Model/explanation artifact identity mismatch; retrain the model')
    return pipeline, {**report, 'state': 'loaded'}


def fit_evaluate(training, testing, key, progress=None):
    pipeline, name, selection, fitting, validation = select_model(training, progress)
    identity = dict(model_name=name, model_version=str(uuid4()), dataset_fingerprint=key)
    background = fitting[FEATURES].sample(min(48, len(fitting)), random_state=42).reset_index(drop=True)
    pipeline.shipment_metadata_ = {**identity, 'background': background,
                                   'supported_scheduled_days': sorted(fitting.scheduled_days.unique().tolist()),
                                   'explanation_version': EXPLANATION_VERSION}
    if progress:
        progress(stage='Explaining selected model on reserved validation orders')
    sample = pd.concat([group.sample(min(len(group), max(1, int(2000 * len(group) / len(validation)))), random_state=42)
                        for _, group in validation.groupby('delayed')])
    explanation = global_importance(pipeline, sample[FEATURES], sample.delayed, identity)
    explanation.update(start=str(validation.order_date.min()), end=str(validation.order_date.max()))
    explanation['shap'] = global_shap(pipeline, sample.sample(min(96, len(sample)), random_state=42), identity)
    threshold = selection['threshold_selection']['threshold']
    pipeline.shipment_metadata_.update(threshold=threshold, global_explanation=explanation)
    # Final outcomes become accessible only AFTER all selection and explanation work.
    testing = testing() if callable(testing) else testing
    if testing.delayed.nunique() != 2:
        raise ValueError('Both classes are required in final chronological test data')
    probability = pipeline.predict_proba(testing[FEATURES])[:, 1]
    metrics = scores(testing.delayed.astype(int), probability, threshold)
    y = fitting.delayed.astype(int)
    report = dict(state='trained', model=name, model_version=identity['model_version'], fingerprint=key,
                  trained_at=datetime.now(timezone.utc).isoformat(), metrics=metrics, confusion_matrix=metrics['confusion_matrix'],
                  threshold=threshold, selection=selection,
                  split='Earlier 80%: expanding validation plus reserved explanation block. Final later 20%: evaluated once after selection.',
                  train_rows=len(fitting), test_rows=len(testing), train_delay_rate=float(y.mean()), test_delay_rate=float(testing.delayed.mean()),
                  majority_baseline_accuracy=float((testing.delayed == int(y.mean() >= .5)).mean()),
                  train_start=str(fitting.order_date.min()), train_end=str(fitting.order_date.max()),
                  test_start=str(testing.order_date.min()), test_end=str(testing.order_date.max()), features=FEATURES,
                  encoded_feature_names=pipeline.named_steps['preprocess'].get_feature_names_out().tolist(),
                  global_explanation=explanation, explanation_rows=len(sample), explanations=explanation['features'])
    report['label_definition'] = '1 = actual_days > scheduled_days; 0 = on time or early. Canceled and suspected-fraud orders excluded.'
    return pipeline, report


def train_or_load(df, force=False, progress=None):
    key = fingerprint(df)
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.ARTIFACT_DIR / f'model-{key}.joblib'
    if path.exists() and not force:
        pipeline, report = load_artifact(path, key)
        if pipeline.shipment_metadata_.get('explanation_version') != EXPLANATION_VERSION or 'shap' not in report['global_explanation']:
            if progress:
                progress(stage='Refreshing SHAP for the existing fitted model; no model retraining')
            report = deepcopy(report)
            version = str(uuid4())
            identity = dict(model_name=report['model'], model_version=version, dataset_fingerprint=key)
            observations = (df.filter((F.col('order_date') >= report['global_explanation']['start']) &
                                     (F.col('order_date') <= report['global_explanation']['end']))
                .orderBy(F.xxhash64('order_id'), 'order_id').limit(96).select(*FEATURES).toPandas())
            pipeline.shipment_metadata_.update(identity)
            report['model_version'] = version
            report['global_explanation'].update(identity)
            report['global_explanation']['shap'] = global_shap(pipeline, observations, identity)
            pipeline.shipment_metadata_.update(global_explanation=report['global_explanation'], explanation_version=EXPLANATION_VERSION,
                supported_scheduled_days=[float(r[0]) for r in df.select('scheduled_days').distinct().orderBy('scheduled_days').collect()])
            report['label_definition'] = '1 = actual_days > scheduled_days; 0 = on time or early. Canceled and suspected-fraud orders excluded.'
            temp = path.with_suffix('.tmp')
            joblib.dump(dict(pipeline=pipeline, report=report), temp)
            os.replace(temp, path)
        return pipeline, report
    if df.count() < 80:
        raise ValueError('At least 80 eligible orders required for chronological tuning and explanations')
    cutoff = df.select(F.col('order_date').cast('long').alias('t')).approxQuantile('t', [.8], .001)[0]
    train, test = df.filter(F.col('order_date').cast('long') < cutoff), df.filter(F.col('order_date').cast('long') >= cutoff)
    cap = max(config.MODEL_MAX_ROWS, 80)
    def bounded(part, limit):
        return part.orderBy(F.xxhash64('order_id'), 'order_id').limit(limit).select('order_date', 'delayed', *FEATURES).toPandas()
    training = bounded(train, int(cap * .8))
    pipeline, report = fit_evaluate(training, lambda: bounded(test, int(cap * .2)), key, progress)
    report.update(available_train_rows=train.count(), available_test_rows=test.count())
    temp = path.with_suffix('.tmp')
    joblib.dump(dict(pipeline=pipeline, report=report), temp)
    os.replace(temp, path)
    return pipeline, report


def predict(pipeline, values):
    values = values.copy()
    date = values.pop('order_date')
    supported = pipeline.shipment_metadata_.get('supported_scheduled_days')
    if values['scheduled_days'] not in range(8):
        raise PredictionInputError('Scheduled duration must be a whole number from 0 to 7 days')
    schedule_note = ''
    if supported is not None and values['scheduled_days'] not in supported:
        schedule_note = ' This scheduled duration was not observed in the fitting data; its estimate is less reliable and does not establish performance for this duration.'
    values.update(day_of_week=(date.weekday() + 1) % 7 + 1, month=date.month)
    observation = pd.DataFrame([values], columns=FEATURES)
    explanation = local_explanation(pipeline, observation)
    probability = float(pipeline.predict_proba(observation)[0, 1])
    threshold = pipeline.shipment_metadata_['threshold']
    return dict(delay_probability=probability, predicted_delayed=probability >= threshold, threshold=threshold,
                model_name=explanation['model_name'], model_version=explanation['model_version'],
                dataset_fingerprint=explanation['dataset_fingerprint'], local_explanation=explanation,
                recommendations=recommend(probability, threshold, explanation),
                scope='Historical risk conditional on shipment proceeding; SHAP and rule-based suggestions describe model associations, not causes or guarantees' + schedule_note)
