import hashlib
import json
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from pyspark.sql import functions as F
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
from sklearn.inspection import permutation_importance
from app import config

NUMERIC = ["scheduled_days", "quantity", "net_sales", "item_count", "day_of_week", "month"]
CATEGORICAL = ["market", "region", "customer_segment", "payment_type"]
FEATURES = NUMERIC + CATEGORICAL


def fingerprint(df):
    # Commutative content digest: independent of CSV row ordering and Spark partitions.
    digest = F.sha2(F.to_json(F.struct(*[F.col(c) for c in sorted(df.columns)])), 256)
    stats = df.select(digest.alias("h")).agg(F.count("*").alias("n"),
        F.min("h").alias("min"), F.max("h").alias("max"),
        F.sum(F.conv(F.substring("h", 1, 15), 16, 10).cast("decimal(38,0)")).alias("sum1"),
        F.sum(F.conv(F.substring("h", 16, 15), 16, 10).cast("decimal(38,0)")).alias("sum2")).first().asDict()
    return hashlib.sha256(json.dumps([stats, config.PIPELINE_VERSION, config.MODEL_MAX_ROWS, sklearn.__version__],
                                     sort_keys=True, default=str).encode()).hexdigest()


def train_or_load(df, force=False):
    key = fingerprint(df)
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.ARTIFACT_DIR / f"model-{key}.joblib"
    if path.exists() and not force:
        artifact = joblib.load(path)  # Only application-owned local artifacts; never user uploads.
        return artifact["pipeline"], {**artifact["report"], "state": "loaded"}
    n = df.count()
    if n < 50:
        raise ValueError("At least 50 eligible orders are required for model evaluation")
    # Cut on an actual timestamp and never split orders sharing that timestamp.
    cutoff_seconds = df.select(F.col("order_date").cast("long").alias("t")).approxQuantile("t", [0.8], 0.001)[0]
    train = df.filter(F.col("order_date").cast("long") < cutoff_seconds)
    test = df.filter(F.col("order_date").cast("long") >= cutoff_seconds)
    train_total, test_total = train.count(), test.count()
    if min(train_total, test_total) < 10:
        raise ValueError("Insufficient distinct dates for a chronological holdout")
    cap = max(config.MODEL_MAX_ROWS, 50)
    def bounded(part, limit):
        return part.orderBy(F.xxhash64("order_id"), "order_id").limit(limit).select(
            "order_date", "delayed", *FEATURES).toPandas()
    training = bounded(train, int(cap * .8))
    testing = bounded(test, max(10, int(cap * .2)))
    X, y = training[FEATURES], training.delayed.astype(int)
    Xt, yt = testing[FEATURES], testing.delayed.astype(int)
    if y.nunique() < 2 or yt.nunique() < 2:
        raise ValueError("Both classes are required in the chronological training and test partitions")
    preprocess = ColumnTransformer([("numeric", StandardScaler(), NUMERIC),
                                   ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)])
    pipeline = Pipeline([("preprocess", preprocess),
                         ("classifier", LogisticRegression(max_iter=1500, random_state=42))])
    pipeline.fit(X, y)
    pred, prob = pipeline.predict(Xt), pipeline.predict_proba(Xt)[:, 1]
    metrics = {"accuracy": accuracy_score(yt, pred), "precision": precision_score(yt, pred, zero_division=0),
               "recall": recall_score(yt, pred, zero_division=0), "f1": f1_score(yt, pred, zero_division=0),
               "roc_auc": roc_auc_score(yt, prob)}
    explain_x = Xt.sample(min(2000, len(Xt)), random_state=42)
    importance = permutation_importance(pipeline, explain_x, yt.loc[explain_x.index],
                                       scoring="roc_auc", n_repeats=3, random_state=42, n_jobs=1)
    report = {"state": "trained", "model": "Logistic regression", "fingerprint": key,
              "trained_at": datetime.now(timezone.utc).isoformat(), "metrics": metrics,
              "confusion_matrix": confusion_matrix(yt, pred, labels=[0, 1]).tolist(), "threshold": .5,
              "split": "Chronological: earlier 80% / later 20%, shared timestamps kept together",
              "train_rows": len(y), "test_rows": len(yt), "available_train_rows": train_total,
              "available_test_rows": test_total, "train_delay_rate": float(y.mean()),
              "test_delay_rate": float(yt.mean()), "majority_baseline_accuracy": float((yt == int(y.mean() >= .5)).mean()),
              "train_start": str(training.order_date.min()), "train_end": str(training.order_date.max()),
              "test_start": str(testing.order_date.min()), "test_end": str(testing.order_date.max()),
              "explanation_rows": len(explain_x), "features": FEATURES,
              "explanations": sorted([{"feature": f, "importance": float(m), "std": float(s)}
                  for f, m, s in zip(FEATURES, importance.importances_mean, importance.importances_std)],
                  key=lambda x: x["importance"], reverse=True)}
    temp = path.with_suffix(".tmp")
    joblib.dump({"pipeline": pipeline, "report": report}, temp)
    os.replace(temp, path)
    return pipeline, report


def predict(pipeline, values):
    date = values.pop("order_date")
    values["day_of_week"] = (date.weekday() + 1) % 7 + 1
    values["month"] = date.month
    probability = float(pipeline.predict_proba(pd.DataFrame([values], columns=FEATURES))[0, 1])
    return {"delay_probability": probability, "predicted_delayed": probability >= .5, "threshold": .5,
            "scope": "Risk conditional on the order proceeding to shipment; not a delivery guarantee"}
