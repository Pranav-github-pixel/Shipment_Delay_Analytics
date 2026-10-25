# Shipment Delay Analytics

## Purpose and layout
React/Vite dashboard → FastAPI → PySpark SQL order analytics; Scikit-learn logistic regression and Random Forest compared for order-time delay risk, with the validation winner used for predictions. Local mode reads the same CSV through Spark; HDFS mode reads through the Hadoop filesystem client. There is no automatic fallback between modes.

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

Delay Analytics also displays a region × shipping-mode heatmap from Spark SQL. Each cell reports eligible count and delayed fraction, respects the same region/mode/date filters, marks fewer than 30 orders and distinguishes absent combinations from zero delay. The API exposes these cells in `analytics.heatmap`. Backend aggregation/filter/empty-state tests, the frontend build and live browser checks passed. DA3 deliverables under `deliverables/DA3` include the 10-page Word report and 12-slide presentation, based on current API results and actual dashboard screenshots; the supplied DA2 PDF controls formatting only.

Below the heatmap, a Python-rendered SVG world map aggregates eligible orders by `Order Country` and sizes circles by delayed count. Natural Earth 5.1.2 country outlines and country/map-unit label points are bundled in `backend/app/assets/world_countries.json` (public domain, source https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson). Spanish destination names are normalized against its localized names. Points are representative country anchors, not individual coordinates: DataCo's Latitude/Longitude describe the store and are not used as delivery locations. Optional country metadata stays in a separate order-level DataFrame; eligible/model rows, features and fingerprint remain unchanged. Missing/conflicting/unmatched destinations remain in totals and appear in coverage diagnostics. `GET /api/analytics/map` uses the dashboard's region/mode/date filters, caches eight results by ingestion ID and filter, and invalidates on successful processing. Its sandboxed SVG frame uses no scripts or external map tiles; an accessible table supplies exact rates/counts. All 164 destination labels in the supplied file resolve. The map is verified with 62,897 eligible orders and 36,048 delays, and the 39-test backend suite and frontend build pass.

Initial prediction-form loading remains unchanged at the user's request. `/prediction-options` still executes five dimension-distinct actions, a market-region collection and distinct net-sales count/sort actions on each form mount, under the shared Spark lock. The net-sales catalog is now unused by the typed input. A future performance fix should cache the catalog by ingestion/model identity and omit the unused amount scan; existing external Google Fonts requests can also affect initial page load. No loading optimization was implemented as part of the geographic map addition.

Prediction uses only order-time features: scheduled days, total quantity, net sales, item count, order weekday/month, market, destination region, customer segment and payment type. Shipping mode remains analytical only: it maps exactly to scheduled days (0/1/2/4) in this dataset, so including both duplicates the same information. IDs, actual duration, shipping date, delivery status, order outcome/status and profit are excluded. Calendar values derive from the order timestamp. Prediction is conditional on shipment proceeding, not a cancellation forecast.

Orders split chronologically at the approximate 80th percentile timestamp, keeping ties together. Within the bounded earlier 80%, two expanding folds fit on the earliest 45%/65% and validate on the next 20% each. The latest 15% is reserved exclusively for explanations. The winner refits on the first 85% of this development partition; explanation observations remain unseen by it. Final-test rows are extracted only after model, feature and threshold selection and global explanations finish. Historical holdout results were already inspected in earlier project versions; this implementation excludes them from all selection, but confirmation on genuinely new orders still requires fresh data.

Compact search: logistic regression C=1/0.1; Random Forest 200 trees, depth/leaf settings 16/5 versus 10/20, square-root feature sampling and two workers. Both use seed 42 and no class reweighting. Logistic regression scales numerics; both one-hot encode categoricals inside independently fitted pipelines. Highest mean validation ROC-AUC wins (exact ties follow stable simpler-first order), aligning selection with risk ranking. Each family's best numeric configuration also tests weekday/month sine-cosine encoding and, separately, net value per unit/per line and units per line. Added features require >=0.002 mean AUC gain with no fold losing >0.01. These basket features need no new form inputs; arbitrary product-category labels and customer coordinates are avoided because destination meaning/order aggregation is ambiguous. Extra models were unnecessary after these controlled comparisons.

Threshold search uses only pooled forward-validation probabilities over 0.25–0.75 in steps of 0.025. It accepts an F1 gain >=0.005 only with accuracy loss <=0.005 and precision loss <=0.05 relative to threshold 0.5; otherwise 0.5 remains. This guards against majority-positive policies whose apparently higher F1 merely flags almost everything. These validation-only operating constraints substitute for unavailable intervention costs; they are not a claim about optimal business cost. Candidate tables show metrics at 0.5; a separate validation table shows the threshold trade-off. Final metrics use the selected threshold.

Only allowlisted order-time model columns enter Pandas. At most `MODEL_MAX_ROWS` (default 100,000) are extracted, deterministically hash-ranked separately within earlier/later partitions with an 80/20 budget. Available/used counts, class proportions, majority baseline, accuracy, precision, recall, F1, ROC-AUC and confusion matrix are reported. Every chronological validation/explanation block requires both classes; insufficient data leaves the model unavailable while analytics remain usable.

Global explanation: interventional Tree SHAP explains the selected forest's class-1 probability using 32 deterministic training-reference orders. Cached global mean absolute grouped SHAP is calculated on up to 96 reserved explanation-validation observations, never final test. Encoded categories and calendar representations are summed into original input groups; basket value ratios belong to order value, units-per-line to basket size. Variation is standard deviation across explained orders, not repeat uncertainty. Logistic regression uses Linear SHAP in log-odds space if selected. Method: https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html . The separate five-repeat grouped permutation ROC-AUC diagnostic remains available for validation comparison.

Local SHAP displays the reference base, signed feature-group contributions and observed inputs. The backend verifies that base plus all contributions reconstructs probability (or log-odds followed by sigmoid for a linear model). Positive increases modeled risk, negative decreases it; neither is causal evidence. Explanation objects are cached per pipeline/version. The existing fitted model can receive a SHAP artifact upgrade with a new UUID and unchanged parameters/evaluation, avoiding unnecessary retuning or test reuse.

Predefined operator recommendations use the predicted class and positive actionable SHAP factors. They cover dispatch readiness, destination review, basket capacity, handling and operating calendar; below-threshold orders receive routine monitoring. Payment/customer attributes do not trigger requests to change those attributes. Every action exposes its rule/trigger and is a review suggestion, never a promised risk reduction. No rule recommends extending delivery promises to manipulate the score.

Prediction inputs allow whole scheduled days 0–7 and dataset-backed dropdowns for market/region/segment/payment. Date, quantity, item count and net sales are entered directly; net sales accepts non-negative decimal amounts. Regions depend on market. Changing input clears prediction/summary. Predictions for scheduled durations absent from model-fitting data carry a reliability notice; offering those inputs does not add training evidence or validate accuracy for them. The API rejects fractions and values outside 0–7.

Atomic Joblib artifacts in `artifacts/` contain the fitted pipeline, UUID model version, threshold, all search/validation results, parameters, input/encoded feature metadata, reference rows and cached global explanation. Keys include processed-data digest, pipeline version, sample cap and sklearn version; consequential algorithm changes bump the pipeline version. Loading validates explanation/model/dataset/threshold identity. Forced retraining generates a new UUID and explanations even for identical data. Only trusted application-owned files are loaded. Dataset state is in memory and requires processing after restart; matching artifacts then load without retraining.

## API and operation
Run a **single Uvicorn worker**, without reload during processing. An in-process worker thread handles ingestion/training; a lock serializes Spark operations and prevents concurrent ingestion. Status stays responsive. Successful datasets publish atomically; a failed ingest retains the previous successful dataset. Model failure is separately reported and does not hide successful analytics. This intentionally is not a distributed job service.

- `GET /api/status`: mode/source, job, quality and model state.
- `POST /api/ingest?force_retrain=false`: HTTP 202 with job ID; poll status. Concurrent start returns 409.
- `GET /api/analytics?region=...&shipping_mode=...&start=YYYY-MM-DD&end=YYYY-MM-DD`: combined filters, inclusive dates. Model/quality are dataset-wide, not filter-dependent.
- `GET /api/model`; `GET /api/model/explanations`; `POST /api/predict`: model/search report, persisted global explanation and validated prediction with local explanation. Explanation identity includes model name, version and dataset fingerprint. Missing/mismatched explanations return 503. Global results are not recomputed on render. Model Explainability reloads on model-version changes and prediction forms reset; publication atomically updates the active pipeline/report. Schemas are in `/docs`.
- `GET /api/prediction-options?price_page=0`: scheduled days 0–7 with separate observed coverage; other dropdowns use observed values, with paged amounts retained for API clients.
- `GET /api/assistant/status`; `POST /api/predict/summary`: optional Groq configuration status and explicitly requested operator narrative. Summary requests include original order inputs and expected model version; the server recomputes prediction/SHAP/rules, rejecting stale models. The adjacent Generate summary button stays disabled until prediction; no automatic generation.
- `POST /api/query/natural`: Groq receives only the current shipments schema/categories and question, returns SQL, and the existing validator restricts it before Spark execution. Dataset changes during generation cause 409. The SQL page offers Direct SQL/Natural language, shows generated SQL and actual Spark results, and allows editing/saving generated SQL. The LLM does not supply result values.
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

Application configuration uses environment variables: `STORAGE_MODE=local|hdfs`, `DATASET_PATH`, `HDFS_URI` (hdfs://localhost:9000), `HDFS_DATASET_PATH`, `ARTIFACT_DIR`, `MODEL_MAX_ROWS`, `SPARK_MASTER` (local[2]), `SPARK_LOCAL_DIR`, `SPARK_DRIVER_MEMORY` (2g), `JAVA_HOME`, `HADOOP_HOME`, `CORS_ORIGINS`. Frontend `/api` uses the Vite proxy; `API_PROXY_TARGET` changes its upstream and `VITE_API_BASE` changes the browser API base. A production static host must proxy `/api` or set VITE_API_BASE at build time.

Only Groq settings also read the ignored project-root `.env` on demand: `GROQ_API_KEY` and `GROQ_MODEL` (default `openai/gpt-oss-20b`); environment values take precedence. Keys never reach the frontend or prompts. Groq summarizes server-computed facts and generates candidate SQL via JSON responses, validated locally. Requests have a 25-second timeout; missing credentials, unavailable models, malformed responses and rate limits produce clear errors while local prediction/direct SQL remain usable. The configured model was checked against the account's available models. Network-restricted environments must allow the backend to reach api.groq.com. Documentation: https://console.groq.com/docs/openai .

HDFS demonstration, with Docker Desktop running:
```powershell
.venv\Scripts\python.exe start_hdfs.py
.\scripts\start-backend.ps1 -Mode hdfs
```
The helper starts Compose, checks a live DataNode and safemode exit, uploads the real CSV, verifies the destination and exits nonzero on failure. Existing exposed DataNode hostname `localhost` supports a host-native Spark driver; the container-side upload explicitly uses the DataNode's Docker-network IP. Remote or containerized Spark requires a reachable advertised hostname. This single-DataNode demonstration provides no replication redundancy. No silent local fallback. NameNode UI: http://localhost:9870 .

## Checks and current environment
```powershell
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm.cmd run build
```
Tests locate project-local Java if present. Spark tests require Java and on Windows the Hadoop native helpers. Fixtures verify whole-order cleaning, denominators, empty results, restricted SQL, API errors, chronological splitting, bounded extraction and artifact reload/prediction equivalence.

Verified on Windows: all 35 backend tests pass, including genuine SHAP additivity/grouping, recommendation triggers, Groq failures, SQL restrictions, stale-model handling and observed-value paging; frontend production build passes. Real data yields 62,897 eligible orders and 36,048 delays. Same-window mean validation AUC: baseline logistic 0.70520, C=0.1 0.70518; baseline forest 0.73993, shallower forest 0.73955. Cyclical AUC: logistic 0.70510/forest 0.73969; basket AUC: logistic 0.70630/forest 0.74048. None meets the feature-retention gain rule. The original numeric forest (200 trees, depth 16, leaf 5) and threshold 0.5 remain selected: ranking gains did not imply a material accuracy improvement, and aggressive F1 thresholds collapsed toward majority-positive decisions on validation.

The final forest fits 42,726 orders, with 7,540 reserved for explanations (1,999 stratified observations used). On 12,631 final-test orders: ROC-AUC 0.74816, accuracy 0.69464, precision 0.80677, recall 0.61674, F1 0.69907; majority baseline 0.57509. Confusion matrix [[4294,1073],[2784,4480]] uses rows actual/columns predicted, on-time then delayed. Differences from earlier model versions are small and reflect changed fit/explanation allocation; they are not evidence of a substantial model improvement. Global importance's strongest group is scheduled shipping days. Model selection does not use these final-test scores.

Windows runtime notes: the existing `.venv` uses Python 3.12 supplied by the bundled runtime; a global `py` launcher is not installed. Java 17 is installed under `.runtime`. Spark scratch files default to `.runtime/spark` (override `SPARK_LOCAL_DIR`). Spark 3.5's Windows batch launcher requires `TEMP` without spaces; keep the Windows default or set `TEMP` and `TMP` to a writable path without spaces. Docker Desktop disk-image storage was relocated, with user authorization, to `D:\DockerDesktopWSL`; the original settings backup is stored there. This is a machine setting, not an application requirement.

Browser integration checks use installed Google Chrome: with both servers running and processing complete, run `npm.cmd run test:e2e` from `frontend`. The real browser flow passed dropdown prediction, SHAP, recommendations, an explicitly requested Groq summary, input-change invalidation, natural-language SQL producing the genuine 62,897-order count, direct SQL/save/delete/error handling and responsive layouts. It verifies no summary request occurs automatically. Screenshots were inspected. SHAP and python-dotenv are the added dependencies; `pip check` passes.

Machine-specific limitation: Docker Desktop 4.48 intermittently fails on restart with stale `dockerInference` / secrets-engine Unix sockets. Recovery used a full Docker stop, termination of only the `docker-desktop` WSL distribution, and renaming the exact `%LOCALAPPDATA%\Docker\run` and `%LOCALAPPDATA%\docker-secrets-engine` directories to backups before restarting. These backups remain in place; Docker images/volumes were not reset. If this error recurs, resolve it before the HDFS demo; local mode remains independent of Docker.

The existing HDFS workflow previously passed a full upload/processing check with the 97,106,635-byte CSV and identical local/HDFS order counts. This model/explanation revision was verified with full local Spark data and artifact/API tests; HDFS processing was not rerun for this revision. Deployment beyond the Windows single-node demonstration remains untested.
