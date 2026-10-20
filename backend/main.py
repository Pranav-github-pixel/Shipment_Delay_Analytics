import os
import logging
from datetime import date
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.models.schemas import (QueryRequest, SaveQueryRequest, QueryResponse, PredictionRequest,
                                PredictionResponse, AnalyticsResponse, SystemStatus, IngestResponse, ModelReport)
from app.services import spark_service as service
from app.services.model_service import predict
from app.services.query_manager import get_all_queries, save_query, delete_query


@asynccontextmanager
async def lifespan(app):
    yield
    if service.global_spark is not None:
        service.global_spark.stop()


app = FastAPI(title="Shipment Delay Analytics API", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.exception("Request failed", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Operation failed. Check backend logs for details."})


@app.get("/api/status", response_model=SystemStatus)
def status():
    return service.status()


@app.get("/api/hdfs-status")
def hdfs_status():
    try:
        return service.check_hdfs_status()
    except Exception as exc:
        return {"status": "disconnected", "dataset_exists": False, "message": str(exc)}


@app.post("/api/ingest", status_code=202, response_model=IngestResponse)
def ingest(force_retrain: bool = False):
    try:
        return {"job": service.start_ingestion(force_retrain)}
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/analytics", response_model=AnalyticsResponse)
def analytics(region: str | None = None, shipping_mode: str | None = None,
              start: date | None = None, end: date | None = None):
    if start and end and start > end:
        raise HTTPException(422, "Start date must not be after end date")
    if service.status()["job"]["state"] == "running":
        raise HTTPException(409, "Processing is running; wait for completion")
    try:
        return service.analytics(region, shipping_mode, start, end)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/model", response_model=ModelReport)
def model():
    return service.status()["model"]


@app.post("/api/predict", response_model=PredictionResponse)
def prediction(req: PredictionRequest):
    with service.state_lock:
        pipeline = service.model
    if pipeline is None:
        raise HTTPException(503, "Model unavailable. Process data and inspect model status")
    return predict(pipeline, req.model_dump())


@app.post("/api/query", response_model=QueryResponse)
def run_query(req: QueryRequest):
    if service.status()["job"]["state"] == "running":
        raise HTTPException(409, "Processing is running; wait for completion")
    try:
        return service.execute_spark_query(req.query)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/queries")
def list_queries():
    return {"queries": get_all_queries()}


@app.post("/api/queries")
def create_or_update_query(req: SaveQueryRequest):
    try:
        save_query(req.name, req.query)
        return {"message": "Query saved"}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/queries/{name}")
def remove_query(name: str):
    try:
        delete_query(name)
        return {"message": "Query deleted"}
    except KeyError as exc:
        raise HTTPException(404, "Saved query not found") from exc
