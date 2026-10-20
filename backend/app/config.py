import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
MODE = os.getenv("STORAGE_MODE", "local").lower()
DATASET_PATH = os.getenv("DATASET_PATH", str(PROJECT / "dataset/DataCoSupplyChainDataset.csv"))
HDFS_URI = os.getenv("HDFS_URI", "hdfs://localhost:9000")
HDFS_DATASET_PATH = os.getenv("HDFS_DATASET_PATH", "/user/logistics/project_data/DataCoSupplyChainDataset.csv")
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", str(PROJECT / "artifacts")))
MODEL_MAX_ROWS = int(os.getenv("MODEL_MAX_ROWS", "100000"))
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[2]")
SPARK_LOCAL_DIR = os.getenv("SPARK_LOCAL_DIR", str(PROJECT / ".runtime/spark"))
PIPELINE_VERSION = "orders-v2"
