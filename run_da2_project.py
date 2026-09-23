import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Ensure JAVA_HOME and HADOOP_HOME are set for PySpark
if "JAVA_HOME" not in os.environ and os.path.exists(r"C:\java"):
    os.environ["JAVA_HOME"] = r"C:\java"
    os.environ["PATH"] = r"C:\java\bin;" + os.environ.get("PATH", "")

if "HADOOP_HOME" not in os.environ and os.path.exists(r"C:\hadoop"):
    os.environ["HADOOP_HOME"] = r"C:\hadoop"
    os.environ["PATH"] = r"C:\hadoop\bin;" + os.environ.get("PATH", "")

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when, isnan, dayofweek, to_timestamp
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

def main():
    print("="*65)
    print("DA2: PREDICTIVE SHIPMENT DELAY ANALYTICS & DATA ENGINEERING")
    print("="*65)

    # 1. Initialize Spark Session
    print("\n[1] Initializing PySpark Session...")
    spark = SparkSession.builder \
        .appName("DA2_Shipment_Delay_Analytics") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()
    
    # Disable excessive logging
    spark.sparkContext.setLogLevel("ERROR")

    # 2. HDFS / Dataset Ingestion
    print("\n[2] Ingesting Dataset into Spark...")
    hdfs_path = "hdfs://localhost:9000/user/logistics/project_data/DataCoSupplyChainDataset.csv"
    local_path = "dataset/DataCoSupplyChainDataset.csv"

    try:
        df_spark = spark.read.option("header", "true").option("encoding", "iso-8859-1").csv(hdfs_path, inferSchema=True)
        total_rows = df_spark.count()
        print(f"-> Successfully loaded {total_rows:,} rows from HDFS cluster ('{hdfs_path}')")
    except Exception:
        print(f"-> Notice: HDFS cluster not active on localhost:9000. Ingesting from local path '{local_path}'...")
        df_spark = spark.read.option("header", "true").option("encoding", "iso-8859-1").csv(local_path, inferSchema=True)
        total_rows = df_spark.count()
        print(f"-> Successfully loaded {total_rows:,} rows from storage ('{local_path}')")

    # =========================================================================
    # 3. SPARK DATA ENGINEERING, CLEANING & PREPROCESSING LIFECYCLE
    # =========================================================================
    print("\n[3] Executing Spark Data Engineering & Quality Pipeline...")

    # --- 3.1 Duplicate Record Detection & Handling ---
    print("\n--- [3.1] Duplicate Detection & Deduplication ---")
    df_dedup = df_spark.dropDuplicates()
    dedup_count = df_dedup.count()
    duplicate_rows = total_rows - dedup_count
    print(f"-> Initial Raw Record Count:          {total_rows:,}")
    print(f"-> Duplicate Records Identified:        {duplicate_rows:,}")
    print("-> Applying PySpark .dropDuplicates() across all schema attributes...")
    print(f"-> Clean Unique Records Retained:       {dedup_count:,}")

    # --- 3.2 Missing Value & Null Value Handling ---
    print("\n--- [3.2] Missing Value & Null Audit ---")
    audit_cols = [
        "Type", "Category Name", "Customer Segment", "Department Name", 
        "Market", "Order Region", "Shipping Mode", "Late_delivery_risk"
    ]
    df_audit = df_dedup.select(audit_cols)
    null_counts_expr = [
        count(when(col(c).isNull() | isnan(c), c)).alias(c)
        if df_audit.schema[c].dataType.typeName() in ["double", "float"]
        else count(when(col(c).isNull(), c)).alias(c)
        for c in audit_cols
    ]
    df_audit.select(null_counts_expr).show()

    print("-> Applying Missing Value Strategy:")
    # Strategy A: Imputation (Fill categorical missing segment with modal default)
    df_imputed = df_dedup.fillna({"Customer Segment": "Consumer"})
    print("   1. Imputation: Filled missing 'Customer Segment' entries with default category ('Consumer')")

    # Strategy B: Dropping remaining records with missing routing features
    critical_cols = ["Market", "Order Region", "Shipping Mode", "Category Name", "Department Name", "Type", "Late_delivery_risk"]
    df_clean_nulls = df_imputed.dropna(subset=critical_cols)
    clean_null_count = df_clean_nulls.count()
    dropped_nulls = dedup_count - clean_null_count
    print(f"   2. Dropping: Filtered {dropped_nulls:,} rows lacking critical operational routing features")
    print(f"-> Post-Null Handling Clean Record Count: {clean_null_count:,}")

    # --- 3.3 Domain Row Filtering & Noise Elimination ---
    print("\n--- [3.3] Row Filtering & Operational Noise Elimination ---")
    print("-> Rule 1: Exclude 'CANCELED' orders (cancelled shipments never reach transit phase)")
    print("-> Rule 2: Exclude non-positive sales (Sales > 0 to eliminate cancelled/void transactions)")
    df_filtered = df_clean_nulls.filter((col("Order Status") != "CANCELED") & (col("Sales") > 0))
    filtered_count = df_filtered.count()
    filtered_out = clean_null_count - filtered_count
    print(f"-> Records Filtered Out:  {filtered_out:,} non-operational/cancelled rows")
    print(f"-> Valid Operational Orders Retained: {filtered_count:,}")

    # --- 3.4 PySpark Feature Engineering (Creating New Derived Columns) ---
    print("\n--- [3.4] Feature Engineering (Creating New Derived Columns) ---")
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
            when(dayofweek(to_timestamp(col("order date (DateOrders)"), "M/d/yyyy H:mm")).isin(1, 7), "Weekend").otherwise("Weekday")
        )

    print("-> Engineered 4 New Predictive Features via Spark SQL Functions:")
    print("   * 'Shipping_Speed_Tier'  : Discretized transit SLA timeframe")
    print("   * 'Order_Volume_Tier'    : Order basket size categorization")
    print("   * 'Order_Value_Segment'  : Commercial transaction value tier")
    print("   * 'Weekend_Order'        : Temporal dispatch indicator (Weekend vs Weekday)")
    print("\n-> Sample Preview of Newly Engineered Features:")
    df_featured.select(
        "Days for shipment (scheduled)", "Shipping_Speed_Tier",
        "Order Item Quantity", "Order_Volume_Tier",
        "Sales", "Order_Value_Segment",
        "Weekend_Order", "Late_delivery_risk"
    ).show(5, truncate=False)

    df_clean = df_featured

    # 4. Spark SQL Exploratory Data Analysis (EDA)
    print("\n[4] Performing Spark SQL Exploratory Data Analysis...")
    df_clean.createOrReplaceTempView("shipments")

    # Query 1: Distribution of delayed vs non-delayed
    print("\n--- Query 1: Delay Distribution ---")
    q1 = spark.sql("SELECT Late_delivery_risk, COUNT(*) as count FROM shipments GROUP BY Late_delivery_risk")
    q1.show()
    
    q1_pd = q1.toPandas()
    q1_pd['Status'] = q1_pd['Late_delivery_risk'].map({0: 'On-Time', 1: 'Delayed'})
    plt.figure(figsize=(6,4))
    sns.barplot(x='Status', y='count', data=q1_pd)
    plt.title("Distribution of Delayed vs On-Time Shipments")
    plt.savefig("eda_q1_distribution.png")
    print("-> Saved plot: eda_q1_distribution.png")

    # Query 2: Delay rate by Shipping Mode
    print("\n--- Query 2: Delay Rate by Shipping Mode ---")
    q2 = spark.sql("""
        SELECT `Shipping Mode`, 
               AVG(Late_delivery_risk) as delay_rate,
               COUNT(*) as total_orders
        FROM shipments
        GROUP BY `Shipping Mode`
        ORDER BY delay_rate DESC
    """)
    q2.show()
    
    q2_pd = q2.toPandas()
    plt.figure(figsize=(8,5))
    sns.barplot(x='Shipping Mode', y='delay_rate', data=q2_pd)
    plt.title("Delay Rate by Shipping Mode")
    plt.ylabel("Delay Rate (Proportion)")
    plt.savefig("eda_q2_shipping_mode.png")
    print("-> Saved plot: eda_q2_shipping_mode.png")

    # Query 3: Delay rate by Region
    print("\n--- Query 3: Top 10 Regions by Delay Rate ---")
    q3 = spark.sql("""
        SELECT `Order Region`, 
               AVG(Late_delivery_risk) as delay_rate
        FROM shipments
        GROUP BY `Order Region`
        ORDER BY delay_rate DESC
        LIMIT 10
    """)
    q3.show()
    
    q3_pd = q3.toPandas()
    plt.figure(figsize=(10,6))
    sns.barplot(x='delay_rate', y='Order Region', data=q3_pd, orient='h')
    plt.title("Top 10 Regions by Delay Rate")
    plt.xlabel("Delay Rate (Proportion)")
    plt.savefig("eda_q3_region.png")
    print("-> Saved plot: eda_q3_region.png")

    # Query 4: Delay rate by Engineered Shipping Speed Tier
    print("\n--- Query 4: Delay Rate by Engineered Shipping Speed Tier ---")
    q4 = spark.sql("""
        SELECT `Shipping_Speed_Tier`,
               AVG(Late_delivery_risk) as delay_rate,
               COUNT(*) as order_count
        FROM shipments
        GROUP BY `Shipping_Speed_Tier`
        ORDER BY delay_rate DESC
    """)
    q4.show()

    # 5. Baseline Logistic Regression Model (with Engineered Features)
    print("\n[5] Transitioning to driver-local Pandas for Model Training...")
    modeling_cols = [
        "Type", "Category Name", "Customer Segment", "Department Name", 
        "Market", "Order Region", "Shipping Mode",
        "Shipping_Speed_Tier", "Order_Volume_Tier", "Order_Value_Segment", "Weekend_Order",
        "Late_delivery_risk"
    ]
    df_pandas = df_clean.select(modeling_cols).toPandas()
    
    X = df_pandas.drop("Late_delivery_risk", axis=1)
    y = df_pandas["Late_delivery_risk"]

    categorical_features = [
        "Type", "Category Name", "Customer Segment", "Department Name", 
        "Market", "Order Region", "Shipping Mode",
        "Shipping_Speed_Tier", "Order_Volume_Tier", "Order_Value_Segment", "Weekend_Order"
    ]
    preprocessor = ColumnTransformer(transformers=[("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features)])
    
    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(max_iter=1000, random_state=42))
    ])

    print("-> Splitting Data (80% Train, 20% Test)...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print("-> Training Logistic Regression Model...")
    pipeline.fit(X_train, y_train)
    
    print("-> Evaluating Model...")
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    roc = roc_auc_score(y_test, y_proba)

    print("\n" + "="*45)
    print("MODEL EVALUATION METRICS (Logistic Regression)")
    print("="*45)
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    print(f"ROC-AUC:   {roc:.4f}")
    print("="*45)

    print("\n[6] Pipeline Execution Finished Successfully.")
    spark.stop()

if __name__ == "__main__":
    main()
