# Predictive Shipment Delay Analytics for Logistics Decision Support
## Master Project Handbook: Introduction, Architecture, DA2 Accomplishments & DA3 Future Roadmap

---

## 1. Executive Project Introduction & Business Motivation

### 1.1 Problem Statement
In modern global supply chains and e-commerce networks, delivery punctuality is a primary driver of customer satisfaction, retention, and contractual SLA compliance. Unforeseen delivery delays trigger severe business consequences:
- Financial penalties for breached Service Level Agreements (SLAs).
- Excess inventory holding and safety stock costs.
- Customer churn and brand reputation degradation.
- Reactive dispatching, emergency air freight expenses, and operational chaos.

Most legacy logistics operations rely on **reactive tracking**—detecting that a package is delayed only *after* it fails to arrive at a distribution checkpoint. 

### 1.2 Our Solution
This project, **"Predictive Shipment Delay Analytics for Logistics Decision Support"**, transforms logistics operations from **reactive monitoring to proactive, predictive risk mitigation**. By leveraging Big Data technologies (**Apache Hadoop HDFS**, **Apache PySpark**, **Spark SQL**) and Machine Learning, the system predicts whether an order will experience a shipping delay (`Late_delivery_risk = 1`) at the very moment the order is placed and scheduled for dispatch. This enables logistics managers to:
1. Re-route orders through faster or alternative transit hubs before delays manifest.
2. Prioritize warehouse picking and packing for high-risk delivery routes.
3. Automatically adjust promised customer delivery estimates dynamically.

### 1.3 Dataset Profile
- **Source:** Kaggle DataCo Smart Supply Chain Dataset.
- **Scale:** 180,519 order records across 53 original commercial, operational, and geographic attributes.
- **Target Label:** `Late_delivery_risk` (Binary Classification: `0 = On-Time / Early`, `1 = Late Delivery`).
- **Domain Scope:** Multi-region retail and commercial freight shipments spanning Europe, the Americas, Asia, and Africa.

---

## 2. End-to-End System Architecture

### 2.1 Current DA2 Architecture (Batch Ingestion, Spark Processing & Baseline ML)

```
┌────────────────────────────────────────────────────────────────────────┐
│                      STORAGE & INGESTION LAYER                         │
│                                                                        │
│   [Local Raw CSV: 96 MB] ──► hdfs dfs -put ──► [HDFS Cluster: Port 9000] │
│                                                  /user/logistics/...   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼ (spark.read.csv with ISO-8859-1)
┌────────────────────────────────────────────────────────────────────────┐
│                   DISTRIBUTED DATA ENGINE (PYSPARK 4.2.0)              │
│                                                                        │
│   1. SparkSession Initializer (4GB Driver Memory, ERROR Log Level)    │
│   2. Deduplication (.dropDuplicates across full schema)                │
│   3. Missing Value Strategy:                                           │
│        - Categorical Imputation: Fill missing Segment with 'Consumer'  │
│        - Drop rows with nulls in critical operational routing features │
│   4. Domain Operational Filtering:                                     │
│        - Exclude 'Order Status' == 'CANCELED'                          │
│        - Exclude 'Sales' <= 0 (Filter non-operational void records)    │
│   5. Distributed Feature Engineering (.withColumn & when expressions): │
│        - Shipping_Speed_Tier  (Express / Fast / Standard)              │
│        - Order_Volume_Tier    (Single / Medium / Bulk)                 │
│        - Order_Value_Segment  (High Value / Standard Value)            │
│        - Weekend_Order        (Weekend / Weekday dispatch)             │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
┌────────────────────────────────────┐ ┌─────────────────────────────────┐
│     ANALYTICS & SQL LAYER (EDA)    │ │   PREDICTIVE MODELING LAYER     │
│                                    │ │                                 │
│  Temporary View: "shipments"       │ │  .toPandas() Driver Extraction  │
│  - Query 1: Class Distribution     │ │  ColumnTransformer OneHotEncoder│
│  - Query 2: Shipping Mode Risk     │ │  Stratified 80/20 Train/Test    │
│  - Query 3: Top 10 Regional Delays │ │  Logistic Regression Baseline   │
│  - Query 4: Speed Tier Delay Rates │ │  Metrics: Acc 69.7%, Prec 84.3% │
│  Output: Seaborn / Matplotlib PNGs │ │           Rec 54.9%, AUC 74.1%  │
└────────────────────────────────────┘ └─────────────────────────────────┘
```

---

### 2.2 Future DA3 Target Architecture (Fully Distributed ML & Real-Time Streaming)

```
                                [ IoT & Order Event Stream ]
                                             │
                                             ▼
                                  [ Apache Kafka Topics ]
                                             │
                                             ▼
                                [ Spark Structured Streaming ]
                                             │
      ┌──────────────────────────────────────┴──────────────────────────────────────┐
      │                                                                             │
      ▼                                                                             ▼
[ HDFS / Delta Lake Lakehouse ]                                     [ PySpark MLlib Inference Engine ]
(Historical Storage & Retraining)                                    (Distributed PipelineModel in RAM)
      │                                                                             │
      ▼                                                                             ▼
[ Distributed Model Training ]                                      [ Live Delay Probability Score ]
- VectorAssembler                                                                   │
- PySpark MLlib GBTClassifier / XGBoost                                             ▼
- Spark CrossValidator & ParamGrid Tuning                           [ Real-Time Decision Support API ]
- Class-Weight Rebalancing                                                          │
                                                                                    ▼
                                                                    [ Logistics Dispatch Dashboard ]
                                                                    - Visual Route Delay Heatmaps
                                                                    - Automated SLA Breach Alerts
                                                                    - Re-Routing Recommendations
```

---

## 3. What We Have Done Till Now (DA2 Milestones Accomplished)

| Milestone | Component | What Was Implemented | Result / Verification |
| :--- | :--- | :--- | :--- |
| **1. Storage Setup** | **HDFS Cluster** | Local Hadoop 3.3.6 single-node cluster configured with NameNode and DataNode on Windows; formatted HDFS namespace; created `/user/logistics/project_data/` and loaded CSV via CLI. | Verified with `hdfs dfs -ls /user/logistics/project_data/`. |
| **2. Spark Ingestion** | **PySpark Session** | Configured `SparkSession` with 4GB driver memory. Ingested data directly from `hdfs://localhost:9000/...` with `inferSchema=True` and `encoding="iso-8859-1"`. Added automated fallback to local path. | 180,519 rows loaded into a distributed PySpark DataFrame without schema corruption. |
| **3. Data Quality Pipeline** | **Spark Cleaning** | Implemented a 3-stage cleaning pipeline:<br>1. **Deduplication:** `.dropDuplicates()` across all attributes.<br>2. **Missing Value Strategy:** Imputed missing `Customer Segment` with modal default (`"Consumer"`); dropped rows missing critical routing attributes.<br>3. **Domain Filtering:** Filtered out `Order Status == "CANCELED"` and non-positive `Sales <= 0`. | Zero nulls in key routing features; eliminated non-operational noise. |
| **4. Feature Engineering** | **Spark SQL Expressions** | Engineered 4 domain-specific derived features using `when().otherwise()`:<br>• `Shipping_Speed_Tier`<br>• `Order_Volume_Tier`<br>• `Order_Value_Segment`<br>• `Weekend_Order`. | Enhanced feature space with operational SLA, basket size, and temporal variables. |
| **5. Exploratory Data Analysis** | **Spark SQL Queries** | Registered `createOrReplaceTempView("shipments")` and executed 4 analytical queries. Exported aggregated summaries to Pandas for Seaborn visualization (`eda_q1_distribution.png`, `eda_q2_shipping_mode.png`, `eda_q3_region.png`). | Identified: 54.8% baseline delay rate, **First Class 95.3% delay rate**, and high-risk regions (Central Africa 57.9%, South Asia 56.3%). |
| **6. Machine Learning Pipeline** | **Scikit-Learn Baseline** | Extracted modeling columns via `.toPandas()`, configured `ColumnTransformer` with `OneHotEncoder(handle_unknown="ignore")`, and assembled an end-to-end `Pipeline` with `LogisticRegression(max_iter=1000)`. | Trained on 80% split (144,415 samples), tested on 20% stratified holdout (36,104 samples). |
| **7. Performance Evaluation** | **Model Evaluation** | Evaluated predictions using 5 standard classification metrics:<br>• **Accuracy:** 69.67%<br>• **Precision:** 84.30%<br>• **Recall:** 54.91%<br>• **F1-Score:** 66.50%<br>• **ROC-AUC:** 74.09%. | Established a solid baseline. Documented the trade-off (high precision vs. moderate recall) and identified the Spark-to-Pandas memory bottleneck. |

---

## 4. What We Will Implement in Future (DA3 & Production Roadmap)

### 4.1 Migration to Native PySpark MLlib (Eliminating the Big Data Bottleneck)
* **The Problem in DA2:** Calling `.toPandas()` in DA2 brings all records into driver RAM. This works for 96 MB, but fails for enterprise scale (100 GB+).
* **The DA3 Solution:** Re-architect the machine learning pipeline using **`pyspark.ml`**:
  - `pyspark.ml.feature.StringIndexer` and `OneHotEncoderEstimator` to encode categoricals in distributed partitions.
  - `pyspark.ml.feature.VectorAssembler` to assemble features into dense/sparse vectors across Spark worker nodes.
  - Native distributed model training running on Spark executors without driver RAM exhaustion.

### 4.2 Non-Linear & High-Performance Ensemble Algorithms
* **Random Forest Classifier (`pyspark.ml.classification.RandomForestClassifier`):**
  - Builds an ensemble of decision trees to capture non-linear feature interactions (e.g., Shipping Mode combined with Order Region).
* **Gradient-Boosted Trees (`pyspark.ml.classification.GBTClassifier` / XGBoost on Spark):**
  - Sequentially minimizes pseudo-residuals to dramatically boost **Recall** from 54.9% to $\ge 78\%$, reducing missed delayed shipments.

### 4.3 Automated Hyperparameter Tuning & Cross-Validation
* Implement **`pyspark.ml.tuning.CrossValidator`** with **`ParamGridBuilder`**:
  - Systematically tune tree depth (`maxDepth: [5, 10, 15]`), number of trees (`numTrees: [50, 100, 200]`), and learning rates using 5-fold cross-validation.

### 4.4 Class Imbalance & Cost-Sensitive Threshold Tuning
* Currently, false negatives (missed delays) are more costly to logistics firms than false positives.
* In DA3, we will implement:
  - **Threshold Optimization:** Shift classification threshold from standard $0.5$ down to $0.38\text{--}0.42$ to capture high-consequence delayed orders.
  - **Weighting:** Apply inverse class weights to heavily penalize misclassified late deliveries.

### 4.5 Continuous Numerical Feature Integration
* Expand feature inputs beyond categorical tiers to include:
  - Numerical distance / coordinates (latitude, longitude).
  - Continuous transaction metrics: Discount %, Item Profit Ratio, Product Price.
  - Rolling warehouse historical delay rates by zip code.

### 4.6 Streaming & Real-Time Decision Support Dashboard
* **Real-Time Simulation:** Connect **Apache Kafka** to simulate incoming purchase transactions and stream them into **Spark Structured Streaming**.
* **Interactive UI:** Build a lightweight dashboard (Streamlit or FastAPI) allowing logistics dispatchers to input planned order routes, inspect live delay risk probabilities, and receive automated recommendations.

---

## 5. Team Member Breakdown & Viva Preparation

| Member | Focus Area | Core Responsibilities | Key Technologies |
| :--- | :--- | :--- | :--- |
| **Member 1** | **Data Engineering** | HDFS cluster setup, PySpark ingestion, schema inference, deduplication, missing value strategy (imputation + dropping), operational row filtering | Apache Hadoop 3.3.6 (HDFS), Apache PySpark 4.2.0, JVM / SparkSession |
| **Member 2** | **Data Analytics** | 4 Engineered features derivation, Spark SQL temporary views, analytical aggregations, delay pattern discovery, EDA charts | Spark SQL, PySpark Functions (`when`, `dayofweek`, `to_timestamp`), Seaborn/Matplotlib |
| **Member 3** | **Machine Learning & Integration** | End-to-end ML Pipeline, One-Hot Encoding, train/test split, Logistic Regression, metric evaluation, big-data trade-offs, DA3 roadmap | Scikit-Learn (Pipeline, ColumnTransformer, LogisticRegression), Spark-to-Pandas bottleneck, Spark MLlib |

---

## 6. MEMBER 1: Data Engineering Specialist
> **Scope:** HDFS Architecture + PySpark Session Initialization + Ingestion + Preprocessing Lifecycle

### 6.1 Core Technical Knowledge to Master

#### A. Hadoop HDFS Architecture & Virtual Paths
* **What is HDFS?** Hadoop Distributed File System is a distributed, fault-tolerant, scalable file system designed to store massive datasets across commodity hardware using a master/slave architecture.
* **NameNode vs DataNode:**
  * **NameNode (Master):** Manages file system namespace, directory tree, block mapping metadata, and file access permissions. Holds metadata in RAM for speed and persists it via `fsimage` and `edits` log.
  * **DataNode (Worker):** Stores actual physical data blocks (default block size: 128 MB in Hadoop 2.x/3.x) and performs block creation, deletion, and replication upon NameNode commands.
* **HDFS Ingestion Commands Used:**
  ```bash
  # 1. Create target directory inside HDFS
  hdfs dfs -mkdir -p /user/logistics/project_data

  # 2. Put local CSV file into HDFS cluster
  hdfs dfs -put dataset/DataCoSupplyChainDataset.csv /user/logistics/project_data/

  # 3. Verify file presence, block count, and file size in HDFS
  hdfs dfs -ls -h /user/logistics/project_data/
  ```
* **Port Reference:**
  * `hdfs://localhost:9000` (Default IPC / RPC communication port for HDFS NameNode).
  * Web UI: `http://localhost:9870` (Hadoop 3.x NameNode status monitoring).

#### B. PySpark Session & Driver Configuration
* **Why SparkSession?** In Spark 2.x+, `SparkSession` is the unified entry point for programming with DataFrames and Datasets. It encapsulates `SparkContext`, `SQLContext`, and `HiveContext`.
* **Code Implementation in `run_da2_project.py`:**
  ```python
  spark = SparkSession.builder \
      .appName("DA2_Shipment_Delay_Analytics") \
      .config("spark.driver.memory", "4g") \
      .getOrCreate()
  spark.sparkContext.setLogLevel("ERROR")
  ```
* **Key Arguments to Explain:**
  * `appName`: Logical name visible in the Spark Web UI (`http://localhost:4040`).
  * `spark.driver.memory = "4g"`: Allocates 4 gigabytes of JVM heap memory to the Spark Driver to prevent `OutOfMemoryError` (OOM) when handling 180,519 rows and conversions.
  * `setLogLevel("ERROR")`: Suppresses verbose INFO and WARN messages for clean operational logs.

#### C. Ingestion & Schema Handling
* **Code Implementation:**
  ```python
  df_spark = spark.read \
      .option("header", "true") \
      .option("encoding", "iso-8859-1") \
      .csv("hdfs://localhost:9000/user/logistics/project_data/DataCoSupplyChainDataset.csv", inferSchema=True)
  ```
* **Why `encoding="iso-8859-1"`?** The DataCo dataset contains international customer names, shipping city names, and Latin/Spanish accents that cause UTF-8 decoding exceptions.
* **Why `inferSchema=True`?** Automatically scans data to determine column datatypes (e.g., Integer, Double, Timestamp, String) rather than defaulting every column to String.
* **Fallback Logic:** If the local Hadoop daemon is offline, the code gracefully falls back to local storage path `dataset/DataCoSupplyChainDataset.csv`.

#### D. Preprocessing Lifecycle
1. **Deduplication:**
   ```python
   df_dedup = df_spark.dropDuplicates()
   ```
   * *Explanation:* Compares all columns across the distributed dataset and removes identical duplicate records to prevent skewed distributions.
2. **Missing Value Audit & Strategy:**
   * *Categorical Imputation:*
     ```python
     df_imputed = df_dedup.fillna({"Customer Segment": "Consumer"})
     ```
     Imputes missing segment entries with the most frequent modal class (`"Consumer"`), retaining row integrity.
   * *Critical Row Dropping:*
     ```python
     critical_cols = ["Market", "Order Region", "Shipping Mode", "Category Name", "Department Name", "Type", "Late_delivery_risk"]
     df_clean_nulls = df_imputed.dropna(subset=critical_cols)
     ```
     Rows missing key logistics routing dimensions or the target label (`Late_delivery_risk`) cannot be reasonably guessed without corrupting model supervision.
3. **Domain Filtering (Operational Noise Elimination):**
   ```python
   df_filtered = df_clean_nulls.filter((col("Order Status") != "CANCELED") & (col("Sales") > 0))
   ```
   * *Why exclude CANCELED?* A cancelled order is halted before transit; it never undergoes actual courier logistics and would introduce false negative/positive transit delay artifacts.
   * *Why `Sales > 0`?* Removes zero-value or refund/chargeback void transactions.

### 6.2 Member 1: Expected Viva Questions & Model Answers

**Q1: Why did you use HDFS instead of reading the CSV directly from the local disk?**
> **Answer:** In real-world enterprise supply chains, data arrives from distributed warehouses and IoT tracking systems at massive scale (terabytes to petabytes), which exceeds the disk and memory capacity of a single machine. HDFS splits the file into 128 MB blocks distributed across worker nodes with replication for fault tolerance. By ingesting into HDFS, our architecture is ready to scale horizontally across multi-node clusters.

**Q2: What is the difference between Transformation and Action in PySpark? Which ones did you use?**
> **Answer:** Transformations in Spark are **lazy**; they do not compute results immediately but build a Directed Acyclic Graph (DAG) of execution. Examples we used: `.filter()`, `.dropna()`, `.dropDuplicates()`, `.withColumn()`, and `.select()`. Actions trigger execution of the DAG and return results to the driver or write to storage. Examples we used: `.count()`, `.show()`, and `.toPandas()`.

**Q3: How does PySpark's `.dropDuplicates()` work under the hood?**
> **Answer:** It performs a distributed shuffle operation. Spark partitions the rows using a hash of the selected columns (or all columns by default), sends identical hashes to the same partition/executor, and keeps only the first record while discarding the duplicates.

---

## 7. MEMBER 2: Data Analytics Specialist
> **Scope:** Feature Engineering via Spark SQL Functions + Spark SQL Queries + EDA Insights

### 7.1 Core Technical Knowledge to Master

#### A. The Four Engineered Features (Why & How)
Member 2 must explain the exact business logic and PySpark SQL functions used:

```python
df_featured = df_filtered \
    .withColumn("Shipping_Speed_Tier", 
        when(col("Days for shipment (scheduled)") <= 1, "Express (<=1d)")
        .when(col("Days for shipment (scheduled)") <= 2, "Fast (2d)")
        .otherwise("Standard (3-4d)")
    ) \
    .withColumn("Order_Volume_Tier",
        when(col("Order Item Quantity") == 1, "Single Item")
        .when(col("Order Item Quantity") <= 3, "Medium (2-3)")
        .otherwise("Bulk (4+)")
    ) \
    .withColumn("Order_Value_Segment",
        when(col("Sales") >= 200.0, "High Value (>=200)").otherwise("Standard Value (<200)")
    ) \
    .withColumn("Weekend_Order",
        when(dayofweek(to_timestamp(col("order date (DateOrders)"), "M/d/yyyy H:mm")).isin(1, 7), "Weekend")
        .otherwise("Weekday")
    )
```

| Feature Name | Source Column | Engineering Logic | Business & Predictive Rationale |
| :--- | :--- | :--- | :--- |
| **`Shipping_Speed_Tier`** | `Days for shipment (scheduled)` | `<=1d`: Express<br>`<=2d`: Fast<br>`3-4d`: Standard | Tighter promised SLA windows (1–2 days) put severe pressure on fulfillment centers, dramatically increasing late delivery risk. |
| **`Order_Volume_Tier`** | `Order Item Quantity` | `1`: Single Item<br>`2-3`: Medium<br>`4+`: Bulk | Multi-item and bulk orders take longer to pick, pack, and verify in warehouses, creating fulfillment bottlenecks. |
| **`Order_Value_Segment`** | `Sales` | `>= $200`: High Value<br>`< $200`: Standard Value | High-value packages frequently undergo additional customs checks, security screening, and signature requirements. |
| **`Weekend_Order`** | `order date (DateOrders)` | `dayofweek()` is 1 (Sun) or 7 (Sat) $\rightarrow$ Weekend, else Weekday | Logistics hubs, customs clearance, and freight carrier depots frequently operate with reduced staffing on weekends. |

#### B. Spark SQL Temporary Views & Analytical Queries
To run SQL queries directly on Spark DataFrames without loading data into MySQL/PostgreSQL:
```python
df_clean.createOrReplaceTempView("shipments")
```
* **Temp View Scope:** Session-scoped; it lives in Spark's memory for the duration of the `SparkSession` and is queryable via standard ANSI SQL using `spark.sql()`.

#### C. The Four EDA Queries & Quantitative Insights
* **Query 1: Overall Delay Distribution**
  ```sql
  SELECT Late_delivery_risk, COUNT(*) as count 
  FROM shipments 
  GROUP BY Late_delivery_risk
  ```
  * *Result:* Out of ~180,519 shipments, **~54.8% (98,977) are delayed** and **~45.2% (81,542) are on-time**.
  * *Insight:* Delivery delays are the majority occurrence rather than rare anomalies. This indicates systematic fulfillment/logistics bottlenecks.
* **Query 2: Delay Rate by Shipping Mode**
  ```sql
  SELECT `Shipping Mode`, 
         AVG(Late_delivery_risk) as delay_rate,
         COUNT(*) as total_orders
  FROM shipments
  GROUP BY `Shipping Mode`
  ORDER BY delay_rate DESC
  ```
  * *Result:*
    * **First Class:** **95.3% delay rate** (Extreme bottleneck)
    * **Second Class:** ~77% delay rate
    * **Standard Class:** **38.1% delay rate**
  * *Insight:* First Class promises unrealistically tight delivery windows that couriers consistently fail to meet, while Standard Class allows adequate buffer time.
* **Query 3: Top 10 Geographic Regions by Delay Rate**
  ```sql
  SELECT `Order Region`, AVG(Late_delivery_risk) as delay_rate
  FROM shipments
  GROUP BY `Order Region`
  ORDER BY delay_rate DESC
  LIMIT 10
  ```
  * *Result:* **Central Africa (57.9%)**, **South Asia (56.3%)**, and **East Africa (55.9%)** experience the highest delay rates.
  * *Insight:* Developing regions with less mature highway infrastructure, longer intercontinental routing, and stringent customs checkpoints exhibit elevated delay probabilities.
* **Query 4: Delay Rate by Shipping Speed Tier**
  ```sql
  SELECT `Shipping_Speed_Tier`, AVG(Late_delivery_risk) as delay_rate, COUNT(*) as order_count
  FROM shipments
  GROUP BY `Shipping_Speed_Tier`
  ORDER BY delay_rate DESC
  ```
  * *Insight:* Validates that the engineered feature `Shipping_Speed_Tier` directly stratifies delay risk, confirming its value for downstream machine learning.

### 7.2 Member 2: Expected Viva Questions & Model Answers

**Q1: How does Spark SQL execute a query on a DataFrame under the hood?**
> **Answer:** Spark SQL uses the **Catalyst Optimizer**. When a query is submitted, Catalyst:
> 1. Analyzes the AST (Abstract Syntax Tree) against the catalog schema.
> 2. Applies logical optimizations (such as predicate pushdown and projection pruning).
> 3. Generates multiple physical plans and picks the lowest-cost execution plan using a cost model.
> 4. Generates optimized Java bytecode via Tungsten code generation.

**Q2: Why did you convert the query results to Pandas (`q1.toPandas()`) for plotting?**
> **Answer:** Spark is a distributed computation engine and does not contain native graphical rendering libraries. However, aggregated query results (like group counts and averages) are tiny summary tables (only a few rows). Calling `.toPandas()` brings only this lightweight aggregated summary to the driver node so Seaborn and Matplotlib can render the charts.

**Q3: What was the most significant finding from your EDA?**
> **Answer:** The massive discrepancy across Shipping Modes. First Class shipments experience a staggering 95.3% delay rate compared to 38.1% for Standard Class. This proves that delay risk is predominantly driven by over-promising tight delivery SLAs rather than random transit accidents.

---

## 8. MEMBER 3: Machine Learning & Integration Specialist
> **Scope:** ML Pipeline + One-Hot Encoding + Logistic Regression + Evaluation Metrics + Limitations & DA3 Roadmap

### 8.1 Core Technical Knowledge to Master

#### A. Scikit-Learn Pipeline & ColumnTransformer Architecture
* **Code Structure in `run_da2_project.py`:**
  ```python
  categorical_features = [
      "Type", "Category Name", "Customer Segment", "Department Name", 
      "Market", "Order Region", "Shipping Mode",
      "Shipping_Speed_Tier", "Order_Volume_Tier", "Order_Value_Segment", "Weekend_Order"
  ]

  preprocessor = ColumnTransformer(
      transformers=[("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features)]
  )

  pipeline = Pipeline(steps=[
      ("preprocessor", preprocessor),
      ("classifier", LogisticRegression(max_iter=1000, random_state=42))
  ])
  ```
* **Why OneHotEncoder?** Categorical attributes (e.g., `"First Class"`, `"Europe"`, `"Consumer"`) cannot be directly multiplied by regression coefficients. One-Hot Encoding converts each category into a binary $(0/1)$ vector.
* **Why `handle_unknown="ignore"`?** If an unseen category appears during inference or in the test split, the encoder sets all encoded columns to 0 instead of throwing a fatal error.
* **Why use `Pipeline`?** Prevents data leakage. Preprocessing transformations are fit **strictly** on the training split and applied to the test split during evaluation.

#### B. Train/Test Split & Stratification
```python
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
```
* **80/20 Ratio:** 80% used for model parameter optimization (~144,415 samples), 20% held out for unbiased testing (~36,104 samples).
* **`random_state=42`:** Ensures exact reproducibility across team members and evaluators.
* **`stratify=y`:** Maintains the exact 54.8% delayed vs 45.2% on-time ratio in both the training and testing sets, preventing sampling bias.

#### C. Logistic Regression Math & Behavior
* **Mathematical Formula:**
  $$P(Y=1|X) = \frac{1}{1 + e^{-z}} = \sigma(w^T X + b)$$
  Where $z = w_1 x_1 + w_2 x_2 + \dots + w_n x_n + b$.
* The model fits weights $w$ using maximum likelihood estimation (Log-Loss).
* If $P(Y=1|X) \ge 0.5$, the shipment is classified as `Delayed (1)`.

#### D. Model Evaluation Metrics (Actual Values & Interpretation)

| Metric | Measured Value | Formula | Operational Meaning in Logistics |
| :--- | :--- | :--- | :--- |
| **Accuracy** | **69.67%** | $\frac{TP + TN}{TP + TN + FP + FN}$ | Out of all shipment predictions, ~69.7% of on-time and delayed statuses were correctly predicted. |
| **Precision** | **84.30%** | $\frac{TP}{TP + FP}$ | When the model sounds an alarm predicting a delay, it is correct **84.3%** of the time. High precision avoids false alarms for logistics dispatchers. |
| **Recall** | **54.91%** | $\frac{TP}{TP + FN}$ | The model identifies **54.9%** of actual delayed shipments, missing ~45.1% of delays. |
| **F1-Score** | **66.50%** | $2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$ | Harmonic mean balancing precision and recall. |
| **ROC-AUC** | **74.09%** | Area under ROC Curve | Measures ability to rank delayed shipments higher than on-time shipments across all probability thresholds. |

#### E. Architectural Limitation: The Spark-to-Pandas Bottleneck
* **The Problem:** In step 5, we call:
  ```python
  df_pandas = df_clean.select(modeling_cols).toPandas()
  ```
  `.toPandas()` collects all distributed records from worker executors across the network and loads them into the single driver node's RAM.
* **Why it worked for DA2:** The dataset is ~180,000 rows (~96 MB), which fits comfortably within the 4 GB driver memory.
* **Why it fails at Big Data scale:** If the dataset grows to 50 million records (50 GB+), calling `.toPandas()` will cause the driver to crash with an `OutOfMemoryError` (OOM).

#### F. DA3 Roadmap (Next Steps & Advanced Architecture)
1. **Transition to Native PySpark MLlib:** Replace Scikit-Learn with `pyspark.ml.classification.LogisticRegression` and `pyspark.ml.feature.VectorAssembler` so model training is distributed across all Spark executors.
2. **Advanced Non-Linear Models:** Implement **Random Forest** and **Gradient-Boosted Trees (GBTClassifier / XGBoost)** to capture complex non-linear feature interactions and raise Recall above 75%.
3. **Threshold Tuning & Class Weighting:** Lower the classification threshold from $0.5$ to $0.4$ or apply class weights to penalize false negatives, boosting recall for high-priority logistics orders.
4. **Incorporate Continuous Numerical Features:** Add historical delivery durations, discount rates, product prices, and customer geographic latitude/longitude.

### 8.2 Member 3: Expected Viva Questions & Model Answers

**Q1: Why is Precision high (84.3%) while Recall is moderate (54.9%)?**
> **Answer:** The baseline Logistic Regression model is conservative. Features like `Shipping Mode = First Class` have a 95% correlation with delays, so whenever the model sees First Class, it predicts delay with high certainty (high precision). However, for Standard Class shipments where delays are driven by complex, subtle factors not captured by linear boundaries, the model plays it safe and predicts on-time, missing actual delayed shipments (low recall).

**Q2: What is Data Leakage and how did your pipeline prevent it?**
> **Answer:** Data leakage occurs when information from the test dataset contaminates the training phase, giving falsely optimistic evaluation metrics. We used Scikit-Learn's `Pipeline` and `ColumnTransformer` along with a stratified `train_test_split`. The `OneHotEncoder` was only fitted on `X_train` (`fit_transform`) and subsequently transformed `X_test` without learning from it.

**Q3: Why can't we use standard Scikit-Learn if the dataset has 100 million records? What will you do in DA3?**
> **Answer:** Scikit-Learn runs on a single node and requires all data to reside in the driver machine's memory. For 100 million rows, the driver will suffer an Out-Of-Memory crash. In DA3, we will migrate to **PySpark MLlib**, which distributes the training of decision trees and logistic regression across worker nodes using resilient distributed datasets (RDDs) and DataFrames.

---

## 9. Comprehensive Cross-Functional Architecture Diagram

```
[HDFS Cluster: localhost:9000]
     │
     ▼ (spark.read.csv with iso-8859-1 & inferSchema)
[SparkSession: 4GB Driver Memory]
     │
     ├─► 1. dropDuplicates() across all columns
     ├─► 2. Missing Value Strategy:
     │      - Impute 'Customer Segment' -> 'Consumer'
     │      - Drop rows with nulls in critical routing columns
     ├─► 3. Domain Filtering:
     │      - Exclude 'Order Status' == 'CANCELED'
     │      - Exclude 'Sales' <= 0
     ├─► 4. Feature Engineering:
     │      - Shipping_Speed_Tier (Express, Fast, Standard)
     │      - Order_Volume_Tier (Single, Medium, Bulk)
     │      - Order_Value_Segment (High Value, Standard Value)
     │      - Weekend_Order (Weekend, Weekday)
     │
     ├─► 5. Spark SQL EDA Views ("shipments"):
     │      - Query 1: 54.8% Delayed vs 45.2% On-Time
     │      - Query 2: First Class (95.3% delay) vs Standard (38.1% delay)
     │      - Query 3: Top delay regions (Central Africa 57.9%, South Asia 56.3%)
     │      - Query 4: Delay distribution across Speed Tiers
     │
     ▼ (toPandas() collection for Scikit-Learn baseline)
[Machine Learning Pipeline]
     ├─► ColumnTransformer: OneHotEncoder(handle_unknown="ignore")
     ├─► train_test_split: 80% Train / 20% Test (Stratified, random_state=42)
     ├─► LogisticRegression(max_iter=1000)
     └─► Metrics: Acc 69.67% | Prec 84.30% | Rec 54.91% | F1 66.50% | AUC 74.09%
```
