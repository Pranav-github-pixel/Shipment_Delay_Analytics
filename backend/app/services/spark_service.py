import os
import shutil
import sys
import logging
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from threading import RLock, Lock, Thread, Timer
from uuid import uuid4
from pyspark.sql import SparkSession, functions as F
import pyspark
from app import config
from app.services.data_pipeline import process
from app.services.model_service import train_or_load

spark_lock = RLock()
state_lock = Lock()
global_spark = None
global_df_clean = None
model = None
quality = None
model_report = {"state": "unavailable", "message": "Process a dataset to train or load a matching model"}
job = {"state": "idle", "stage": "Ready to process"}


def get_spark_session():
    global global_spark
    with spark_lock:
        if global_spark is None:
            if not os.getenv("JAVA_HOME") and not shutil.which("java"):
                raise RuntimeError("Java is unavailable. Set JAVA_HOME to a Java 17 installation")
            os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
            # Spark's Windows launcher fails to discover pip installs in paths with spaces.
            os.environ.setdefault("SPARK_HOME", str(Path(pyspark.__file__).resolve().parent))
            Path(config.SPARK_LOCAL_DIR).mkdir(parents=True, exist_ok=True)
            global_spark = (SparkSession.builder.master(config.SPARK_MASTER).appName("ShipmentDelayAnalytics")
                .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "2g"))
                .config("spark.sql.shuffle.partitions", "8")
                .config("spark.local.dir", config.SPARK_LOCAL_DIR)
                .config("spark.sql.session.timeZone", "UTC")
                .config("spark.sql.ansi.enabled", "false")
                .config("spark.sql.legacy.timeParserPolicy", "CORRECTED")
                .config("spark.hadoop.dfs.client.use.datanode.hostname", "true")
                .config("spark.hadoop.ipc.client.connect.timeout", "5000")
                .config("spark.hadoop.ipc.client.connect.max.retries", "1")
                .getOrCreate())
            global_spark.sparkContext.setLogLevel("ERROR")
        return global_spark


def source_path():
    if config.MODE == "local":
        return config.DATASET_PATH
    if config.MODE == "hdfs":
        return config.HDFS_URI.rstrip("/") + "/" + config.HDFS_DATASET_PATH.lstrip("/")
    raise ValueError("STORAGE_MODE must be local or hdfs")


def check_hdfs_status():
    with spark_lock:
        spark = get_spark_session()
        path = spark._jvm.org.apache.hadoop.fs.Path(config.HDFS_URI.rstrip("/") + "/")
        fs = path.getFileSystem(spark._jsc.hadoopConfiguration())
        fs.getStatus(path)
        dataset = spark._jvm.org.apache.hadoop.fs.Path(config.HDFS_URI.rstrip("/") + "/" + config.HDFS_DATASET_PATH.lstrip("/"))
        return {"status": "connected", "dataset_exists": bool(fs.exists(dataset)), "message": "HDFS RPC succeeded"}


def status():
    with state_lock:
        return {"mode": config.MODE, "source": source_path(), "job": dict(job),
                "data_ready": quality is not None, "quality": quality, "model": model_report}


def update_job(**values):
    with state_lock:
        job.update(values)


def run_ingestion_and_processing(force=False):
    global global_df_clean, model, quality, model_report
    fresh = None
    try:
        with spark_lock:
            update_job(stage="Reading and validating order items")
            spark = get_spark_session()
            raw = (spark.read.option("header", True).option("encoding", "ISO-8859-1")
                   .option("mode", "FAILFAST").option("multiLine", True).csv(source_path()))
            fresh, report = process(raw)
            update_job(stage="Evaluating model on a chronological holdout")
            try:
                new_model, new_model_report = train_or_load(fresh, force)
            except Exception as exc:
                new_model, new_model_report = None, {"state": "unavailable", "message": str(exc)}
            fresh.createOrReplaceTempView("shipments")
            previous = global_df_clean
            if previous is not None and not previous.sameSemantics(fresh):
                previous.unpersist()
            # Replacing a view can invalidate an equivalent cached plan. Materialize
            # the published dataset again before admitting analytical requests.
            fresh.cache().count()
            with state_lock:
                global_df_clean, quality = fresh, report
                model, model_report = new_model, new_model_report
            update_job(state="completed", stage="Dataset ready" if new_model else "Dataset ready; model unavailable")
    except Exception as exc:
        logging.exception("Dataset processing failed")
        if fresh is not None:
            fresh.unpersist()
        if global_df_clean is not None:
            with spark_lock:
                global_df_clean.createOrReplaceTempView("shipments")
        detail = str(exc)
        if "not enough space" in detail.lower() or "no space left" in detail.lower():
            detail = "Disk space exhausted. Free space or configure SPARK_LOCAL_DIR and TEMP on a drive with available space."
        update_job(state="failed", stage="Processing failed; any previous successful dataset remains active", error=detail[:1500])


def start_ingestion(force=False):
    global job
    with state_lock:
        if job["state"] == "running":
            raise RuntimeError("A processing job is already running")
        job = {"id": str(uuid4()), "state": "running", "stage": "Starting", "error": None}
        result = dict(job)
    Thread(target=run_ingestion_and_processing, args=(force,), daemon=True).start()
    return result


def require_data():
    if global_df_clean is None:
        raise RuntimeError("No processed dataset. Start ingestion first")


def serializable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def records(df):
    return [{k: serializable(v) for k, v in row.asDict().items()} for row in df.collect()]


def analytics(region=None, shipping_mode=None, start=None, end=None):
    with spark_lock:
        require_data()
        spark = get_spark_session()
        # Replacing a temporary filtered view can evict the underlying cached plan.
        # Bind literals against the stable published view instead.
        where = """WHERE (:region IS NULL OR region = :region)
            AND (:mode IS NULL OR shipping_mode = :mode)
            AND (:start IS NULL OR TO_DATE(order_date) >= :start)
            AND (:end IS NULL OR TO_DATE(order_date) <= :end)"""
        args = {"region": region, "mode": shipping_mode, "start": start, "end": end}
        overview = records(spark.sql("""SELECT COUNT(*) AS total_orders, COALESCE(SUM(delayed),0) AS delayed_orders,
            AVG(delayed) AS delay_rate, 1 - AVG(delayed) AS on_time_rate,
            AVG(actual_days) AS average_shipping_days, AVG(scheduled_days) AS average_scheduled_days,
            AVG(delay_days) AS average_delay_days FROM shipments """ + where, args=args))[0]
        views = {}
        for name, column in [("regional", "region"), ("shipping", "shipping_mode"),
                             ("temporal", "order_month"), ("segmentation", "customer_segment")]:
            views[name] = records(spark.sql(f"""SELECT {column} AS label, COUNT(*) AS total_orders,
                SUM(delayed) AS delayed_orders, AVG(delayed) AS delay_rate,
                AVG(delay_days) AS average_delay_days FROM shipments {where}
                GROUP BY {column} ORDER BY {column}""", args=args))
        options = {c: [r[0] for r in global_df_clean.select(c).distinct().orderBy(c).collect()]
                   for c in ["region", "shipping_mode"]}
        return {"overview": overview, "views": views, "options": options,
                "definition": "One eligible order is one shipment proxy. On time includes early delivery. Canceled shipping is excluded."}


def execute_spark_query(query):
    from app.services.sql_guard import validate_query
    safe_sql = validate_query(query)
    with spark_lock:
        require_data()
        spark = get_spark_session()
        group = str(uuid4())
        spark.sparkContext.setJobGroup(group, "Read-only analytics", interruptOnCancel=True)
        timer = Timer(30, lambda: spark.sparkContext.cancelJobGroup(group))
        timer.daemon = True
        timer.start()
        try:
            result = spark.sql(safe_sql).limit(101)
            if len(set(result.columns)) != len(result.columns):
                raise ValueError("Use unique column aliases in the result")
            rows = records(result)
            return {"columns": result.columns, "data": rows[:100], "truncated": len(rows) > 100, "limit": 100}
        finally:
            timer.cancel()
            spark.sparkContext.setLocalProperty("spark.jobGroup.id", None)
