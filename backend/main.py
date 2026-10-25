import os
import logging
from datetime import date
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.models.schemas import (QueryRequest, SaveQueryRequest, QueryResponse, PredictionRequest,
                                PredictionResponse, AnalyticsResponse, SystemStatus, IngestResponse, ModelReport, GlobalExplanation,
                                SummaryRequest, SummaryResponse, NaturalQueryRequest, NaturalQueryResponse, GeographicResponse)
from app.services import spark_service as service
from app.services.model_service import predict, PredictionInputError
from app.services import groq_service
from app.services.explainability import explanation_for
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


@app.get('/api/analytics/map', response_model=GeographicResponse)
def geographic_map(region: str | None = None, shipping_mode: str | None = None,
                   start: date | None = None, end: date | None = None):
    if start and end and start > end:
        raise HTTPException(422, 'Start date must not be after end date')
    if service.status()['job']['state'] == 'running':
        raise HTTPException(409, 'Processing is running; wait for completion')
    try:
        return service.geographic_map(region, shipping_mode, start, end)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(503, 'World map unavailable. Check the bundled Natural Earth map asset') from exc


@app.post("/api/predict", response_model=PredictionResponse)
def prediction(req: PredictionRequest):
    with service.state_lock:
        pipeline = service.model
    if pipeline is None:
        raise HTTPException(503, "Model unavailable. Process data and inspect model status")
    try:
        return predict(pipeline, req.model_dump())
    except PredictionInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get('/api/prediction-options')
def prediction_options(price_page: int = Query(default=0, ge=0)):
    if service.status()['job']['state'] == 'running':
        raise HTTPException(409, 'Processing is running; wait for completion')
    try:
        return service.prediction_options(price_page)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/api/assistant/status')
def assistant_status():
    return groq_service.status()


@app.post('/api/predict/summary', response_model=SummaryResponse)
def prediction_summary(req: SummaryRequest):
    with service.state_lock:
        pipeline = service.model
    if pipeline is None:
        raise HTTPException(503, 'Model unavailable. Process data first')
    if pipeline.shipment_metadata_['model_version'] != req.expected_model_version:
        raise HTTPException(409, 'Model changed. Predict again before requesting a summary')
    try:
        result = groq_service.operator_summary(predict(pipeline, req.model_dump(exclude={'expected_model_version'})))
    except PredictionInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (ValueError, groq_service.AssistantUnavailable) as exc:
        raise HTTPException(503, str(exc)) from exc
    with service.state_lock:
        if service.model is not pipeline:
            raise HTTPException(409, 'Model changed during summary generation. Predict again')
    return result


@app.post('/api/query/natural', response_model=NaturalQueryResponse)
def natural_query(req: NaturalQueryRequest):
    initial = service.status()['job']
    if initial['state'] == 'running':
        raise HTTPException(409, 'Processing is running; wait for completion')
    try:
        schema = service.query_schema()
        sql, assistant_model = groq_service.natural_sql(req.question, schema)
        with service.spark_lock:
            current = service.status()['job']
            if current['state'] == 'running' or current.get('id') != initial.get('id'):
                raise HTTPException(409, 'Dataset changed during SQL generation. Please ask again')
            result = service.execute_spark_query(sql)
        return {**result, 'generated_sql': sql, 'question': req.question,
                'provider': 'Groq', 'assistant_model': assistant_model}
    except groq_service.AssistantUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/model/explanations", response_model=GlobalExplanation)
def global_explanations():
    with service.state_lock:
        pipeline = service.model
    if pipeline is None:
        raise HTTPException(503, "Model explanation unavailable. Process data first")
    try:
        return explanation_for(pipeline)
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


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
