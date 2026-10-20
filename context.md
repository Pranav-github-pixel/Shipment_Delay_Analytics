# Shipment Delay Analytics

## Purpose and layout
React/Vite dashboard → FastAPI → PySpark SQL order analytics; Scikit-learn logistic regression for order-time delay risk. Local mode reads the same CSV through Spark; HDFS mode reads through the Hadoop filesystem client. There is no automatic fallback between modes.

- `backend/app/config.py`: environment configuration.
- `backend/app/services/data_pipeline.py`: validation, item deduplication and order aggregation.
- `spark_service.py`: one Spark session, serialized Spark operations, background processing and analytics SQL.
- `model_service.py`: bounded modeling extract, chronological evaluation, artifact persistence and prediction.
- `sql_guard.py` / `query_manager.py`: restricted SQL and atomic JSON saved queries.
- `backend/main.py`, `app/models/schemas.py`: API contracts and validation.
- `frontend/src/App.jsx`, `index.css`: dashboard, actual filters, model/prediction and SQL controls.
- `tests/`: synthetic test fixtures only; application metrics always use the configured dataset.

## Grain, eligibility and features
The supplied CSV has 181,169 item rows, 180,519 distinct item IDs, 65,752 distinct order IDs and 650 exact duplicates. There is no shipment ID. One eligible order is explicitly used as a shipment proxy; never describe item-row counts as shipments. The data spans January 2015–January 2018, with no timezone metadata; timestamps are interpreted as business wall times (Spark UTC to prevent host-timezone shifts).

Exact duplicates are removed first. Conflicting repeated item IDs exclude their entire orders; arbitrarily choosing an item would distort totals. Invalid IDs, dates, nonfinite/negative amounts or durations, nonpositive/nonintegral quantities and invalid targets also exclude the whole affected order. Zero sales is allowed: free items do not imply invalid shipping. Amounts are not labeled with a currency absent from the metadata.

Order timestamps, durations, targets and status fields must agree within an order. A missing dimension can be recovered from another consistent nonmissing value in that order; conflicting nonmissing values exclude the order. Fully missing dimensions become `Unknown`, not an invented customer segment. Item quantities and gross/net sales sum to order totals. Model value is net sales (`Order Item Total`); gross sales remains analytical. Product categories are not assigned arbitrarily to multi-category orders, and arbitrary price/volume tiers are omitted.

Exclude canceled shipping, canceled orders and suspected fraud from delivery-performance denominators. In the supplied data, canceled shipping has target zero even when duration exceeds schedule. Remaining targets must agree with `actual_days > scheduled_days`; inconsistent orders are counted and excluded. Quality diagnostics identify row versus order counts; missing counts precede cleaning, and invalid-row diagnostics overlap.

## Metrics and model
Spark SQL computes overview, region, shipping mode, order-month and customer-segment views. Delay rate = delayed eligible orders / eligible orders. On-time includes early delivery. Average shipping duration uses all eligible orders. Average delay days = mean(max(actual − scheduled, 0)), including zero delay. Empty populations return null rates, not zero. Each comparison displays order counts; small samples are flagged, and associations are not causal claims.

Prediction uses only order-time features: scheduled days, total quantity, net sales, item count, order weekday/month, market, destination region, customer segment and payment type. Shipping mode remains analytical only: it maps exactly to scheduled days (0/1/2/4) in this dataset, so including both duplicates the same information. IDs, actual duration, shipping date, delivery status, order outcome/status and profit are excluded. Calendar values derive from the order timestamp. Prediction is conditional on shipment proceeding, not a cancellation forecast.

Orders are split chronologically at approximately the 80th percentile timestamp, with shared timestamps kept together. This simulates predicting later orders and prevents item siblings appearing in both sets. Numeric standardization and categorical one-hot encoding are fitted on training data only; unknown inference categories are supported. No redundant numeric bins or automatic model tournament. Logistic regression is reproducible; unweighted training retains observed prevalence. Report class proportions and a training-majority baseline instead of claiming imbalance improvements. Classification threshold is 0.5, not tuned on holdout.

Only selected model columns enter Pandas. At most `MODEL_MAX_ROWS` (default 100,000) are extracted, deterministically hash-ranked separately within earlier/later partitions with an 80/20 budget. Available and used counts are reported. Metrics: precision, recall, F1, ROC-AUC, accuracy and confusion matrix (rows actual, columns predicted; order on-time/delayed). Permutation importance reports ROC-AUC decrease and repeat standard deviation on up to 2,000 held-out orders, three repeats; correlated predictors can dilute importance. It is diagnostic, not causal. Both partitions must contain both classes; insufficient data makes the model unavailable while analytics remain usable.

Artifacts are atomic local Joblib files in `artifacts/`, keyed by a commutative processed-data digest, pipeline version, sample cap and sklearn version. Bump `PIPELINE_VERSION` after consequential pipeline/model changes. Only load trusted application-owned artifacts. Reprocessing loads a matching artifact; explicit retraining replaces it. Dataset state is in memory and requires processing after restart; the matching model is then loaded without retraining.

## API and operation
Run a **single Uvicorn worker**, without reload during processing. An in-process worker thread handles ingestion/training; a lock serializes Spark operations and prevents concurrent ingestion. Status stays responsive. Successful datasets publish atomically; a failed ingest retains the previous successful dataset. Model failure is separately reported and does not hide successful analytics. This intentionally is not a distributed job service.

- `GET /api/status`: mode/source, job, quality and model state.
- `POST /api/ingest?force_retrain=false`: HTTP 202 with job ID; poll status. Concurrent start returns 409.
- `GET /api/analytics?region=...&shipping_mode=...&start=YYYY-MM-DD&end=YYYY-MM-DD`: combined filters, inclusive dates. Model/quality are dataset-wide, not filter-dependent.
- `GET /api/model`; `POST /api/predict`: validated order-time input; missing model returns 503. Request schema and examples of field types are in `/docs`.
- `GET /api/hdfs-status`: actual HDFS RPC and dataset-existence check; local mode does not require HDFS.
- `POST /api/query`; `GET/POST /api/queries`; `DELETE /api/queries/{name}`: saved SQL uses JSON, not Markdown. Query only the processed `shipments` view, independent of dashboard filters. Single SELECT, approved aggregate/scalar functions, no joins/CTEs/subqueries/external tables/UDFs. Limit display to 100 rows and cancel Spark jobs after 30 seconds (best effort; not a hard resource sandbox). Use unique output aliases. This is a local demo service, not an authenticated multi-tenant SQL service.

## Windows setup and configuration
Use Python 3.10–3.12, Java 17, Node 22.12+ (or 24), Docker Desktop with Linux containers for HDFS. Verify actual versions before setup. PySpark is pinned to 3.5.7. Java requirements: https://spark.apache.org/docs/3.5.7/api/python/getting_started/install.html .

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
# Set JAVA_HOME to your Java 17 installation if it is not already configured.
.\scripts\start-backend.ps1 -Mode local
# A second terminal:
cd frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Open http://localhost:5173 and click Process dataset. `scripts/start-backend.ps1` uses an existing JAVA_HOME or a project-local `.runtime/jdk-17*`, and the existing `.hadoop/bin` on Windows if HADOOP_HOME is unset. No account-specific path is embedded in application code. Portable Java may be extracted under `.runtime/`; that directory, `.venv/` and artifacts are ignored by Git. The checked-in Hadoop native utilities are Windows-specific; Linux uses its normal Java/Hadoop libraries.

Configuration is read from environment variables (no implicit `.env` loader): `STORAGE_MODE=local|hdfs`, `DATASET_PATH`, `HDFS_URI` (default hdfs://localhost:9000), `HDFS_DATASET_PATH`, `ARTIFACT_DIR`, `MODEL_MAX_ROWS`, `SPARK_MASTER` (local[2]), `SPARK_DRIVER_MEMORY` (2g), `JAVA_HOME`, `HADOOP_HOME`, `CORS_ORIGINS`. Frontend uses `/api` proxied by Vite; `API_PROXY_TARGET` changes the development upstream and `VITE_API_BASE` changes the browser API base. A production static host must proxy `/api` or set VITE_API_BASE at build time.

HDFS demonstration, with Docker Desktop running:
```powershell
.venv\Scripts\python.exe start_hdfs.py
.\scripts\start-backend.ps1 -Mode hdfs
```
The helper starts Compose, checks a live DataNode and safemode exit, uploads the real CSV, verifies the destination and exits nonzero on failure. Existing exposed DataNode hostname `localhost` supports a host-native Spark driver; remote or containerized Spark requires a reachable advertised hostname. No silent local fallback. NameNode UI: http://localhost:9870 .

## Checks and current environment
```powershell
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm.cmd run build
```
Tests locate project-local Java if present. Spark tests require Java and on Windows the Hadoop native helpers. Fixtures verify whole-order cleaning, denominators, empty results, restricted SQL, API errors, chronological splitting, bounded extraction and artifact reload/prediction equivalence.

Verified on this Windows machine: all 18 backend tests pass; the frontend production build passes. Full local Spark ingestion yields 62,897 eligible orders and 36,048 delayed orders (57.31%). The chronological holdout contains 12,631 orders: precision 0.840, recall 0.590, F1 0.693, ROC-AUC 0.721 and accuracy 0.699, compared with majority-baseline accuracy 0.575. These are historical evaluation results, not guarantees for new orders.

Windows runtime notes: the existing `.venv` uses Python 3.12 supplied by the bundled runtime; a global `py` launcher is not installed. Java 17 is installed under `.runtime`. Spark scratch files default to `.runtime/spark` (override `SPARK_LOCAL_DIR`). Spark 3.5's Windows batch launcher requires `TEMP` without spaces; keep the Windows default or set `TEMP` and `TMP` to a writable path without spaces. Docker Desktop disk-image storage was relocated, with user authorization, to `D:\DockerDesktopWSL`; the original settings backup is stored there. This is a machine setting, not an application requirement.

Browser integration checks use installed Google Chrome: with both servers running and processing complete, run `npm.cmd run test:e2e` from `frontend`. The full browser test passed against the real dataset, covering API filters, prediction, saved SQL creation/execution/deletion, invalid SQL rejection and responsive layouts without mocked metrics. Desktop/mobile screenshots were inspected. `npm.cmd audit --omit=dev` reported zero vulnerabilities.
