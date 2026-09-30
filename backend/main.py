from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models.schemas import QueryRequest, SaveQueryRequest
from app.services.spark_service import check_hdfs_status, run_ingestion_and_processing, execute_spark_query
from app.services.query_manager import get_all_queries, save_query, delete_query

app = FastAPI(title="Shipment Delay Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/hdfs-status")
def hdfs_status():
    if check_hdfs_status():
        return {"status": "connected", "message": "HDFS is running"}
    else:
        return {"status": "disconnected", "message": "HDFS is not running"}

@app.post("/api/ingest")
def ingest(random_split: bool = False):
    if not check_hdfs_status():
        raise HTTPException(status_code=503, detail="HDFS is not connected. Please start HDFS before proceeding.")
    try:
        metrics = run_ingestion_and_processing(random_split)
        return {"message": "Ingestion and modeling complete", "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/api/query")
def run_query(req: QueryRequest):
    try:
        return execute_spark_query(req.query)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/queries")
def list_queries():
    return {"queries": get_all_queries()}

@app.post("/api/queries")
def create_or_update_query(req: SaveQueryRequest):
    save_query(req.name, req.query)
    return {"message": "Query saved successfully"}

@app.delete("/api/queries/{name}")
def remove_query(name: str):
    delete_query(name)
    return {"message": "Query deleted successfully"}
