import os
import socket
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when, isnan, dayofweek, to_timestamp
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

global_spark = None
global_df_clean = None

def get_spark_session():
    global global_spark
    if global_spark is None:
        # Override the broken system JAVA_HOME with the actual working Java 17 path you found
        # We wrap it in quotes internally if needed, but PySpark usually handles AppData well
        # if we just give it the exact string without the trailing slash.
        os.environ["JAVA_HOME"] = r"C:\Users\winps\AppData\Local\Programs\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
        
        # Point HADOOP_HOME to our local downloaded winutils
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        hadoop_path = os.path.join(project_root, ".hadoop")
        os.environ["HADOOP_HOME"] = hadoop_path
        os.environ["PATH"] = os.path.join(hadoop_path, "bin") + ";" + os.environ.get("PATH", "")
        
        global_spark = SparkSession.builder \
            .appName("DA2_Shipment_Delay_Analytics_FastAPI") \
            .config("spark.driver.memory", "4g") \
            .config("spark.hadoop.dfs.client.use.datanode.hostname", "true") \
            .getOrCreate()
        global_spark.sparkContext.setLogLevel("ERROR")
    return global_spark

def check_hdfs_status():
    """Checks if HDFS is running by attempting to connect to localhost:9000"""
    try:
        sock = socket.create_connection(("localhost", 9000), timeout=2)
        sock.close()
        return True
    except Exception as e:
        return False

def run_ingestion_and_processing(random_split: bool = False):
    global global_df_clean
    spark = get_spark_session()
    
    hdfs_path = "hdfs://localhost:9000/user/logistics/project_data/DataCoSupplyChainDataset.csv"
    df_spark = spark.read.option("header", "true").option("encoding", "iso-8859-1").csv(hdfs_path, inferSchema=True)
    
    df_dedup = df_spark.dropDuplicates()
    df_imputed = df_dedup.fillna({"Customer Segment": "Consumer"})
    
    critical_cols = ["Market", "Order Region", "Shipping Mode", "Category Name", "Department Name", "Type", "Late_delivery_risk"]
    df_clean_nulls = df_imputed.dropna(subset=critical_cols)
    
    df_filtered = df_clean_nulls.filter((col("Order Status") != "CANCELED") & (col("Sales") > 0))
    
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
    
    global_df_clean = df_featured
    global_df_clean.createOrReplaceTempView("shipments")
    
    modeling_cols = [
        "Type", "Category Name", "Customer Segment", "Department Name", 
        "Market", "Order Region", "Shipping Mode",
        "Shipping_Speed_Tier", "Order_Volume_Tier", "Order_Value_Segment", "Weekend_Order",
        "Late_delivery_risk"
    ]
    df_pandas = df_featured.select(modeling_cols).toPandas()
    
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

    rs = None if random_split else 42
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=rs, stratify=y)
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "total_rows": df_featured.count()
    }
    
    return metrics

def execute_spark_query(query: str):
    if global_df_clean is None:
        raise Exception("Data not ingested yet. Please run ingestion first.")
    
    spark = get_spark_session()
    df_result = spark.sql(query)
    result_pd = df_result.limit(100).toPandas()
    result_pd = result_pd.where(pd.notnull(result_pd), None)
    return {"columns": list(result_pd.columns), "data": result_pd.to_dict(orient="records")}
