import io
import logging
from contextlib import asynccontextmanager
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from httpx import AsyncClient
from openai import AsyncOpenAI

from .config import settings
from .diagnostic_agent import TOOL_SELECTION_SECONDS
from .diagnostic_api import router as diagnostic_router
from .diagnostic_history import DiagnosticHistory
from .knowledge import KnowledgeLibrary
from .knowledge_api import router as knowledge_router
from .schemas import (
    AssetListResponse,
    BatchResponse,
    FleetSummary,
    MachineInput,
    MachineLookupResult,
    PredictionResult,
)
from .service import PredictionService
from .work_orders import WorkOrderStore
from .work_orders_api import router as work_orders_router

logging.basicConfig(
    level=settings.log_level,
    format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger("machineguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    base_url, credential = settings.llm_connection()
    app.state.models = PredictionService(settings)
    app.state.knowledge = KnowledgeLibrary(
        settings.database_path, settings.knowledge_chunk_length, settings.knowledge_chunk_overlap
    )
    app.state.knowledge.initialize()
    app.state.knowledge_upload_limit = settings.knowledge_max_upload_bytes
    app.state.diagnostic_history = DiagnosticHistory(settings.database_path)
    app.state.diagnostic_history.initialize()
    app.state.work_orders = WorkOrderStore(settings.database_path)
    app.state.work_orders.initialize()
    app.state.openai_model = settings.openai_model
    app.state.llm_provider = settings.llm_provider
    key = credential.get_secret_value().strip() if credential else ""
    app.state.openai_client = AsyncOpenAI(
        api_key=key, base_url=base_url, timeout=TOOL_SELECTION_SECONDS, max_retries=0,
        http_client=AsyncClient(follow_redirects=False, timeout=TOOL_SELECTION_SECONDS),
    ) if key else None
    logger.info("model_artifacts_loaded")
    try:
        yield
    finally:
        if app.state.openai_client is not None:
            await app.state.openai_client.close()


app = FastAPI(title="MachineGuard AI API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    logger.warning("request_validation_failed")
    if request.url.path.startswith("/api/v1/diagnostics"):
        return JSONResponse(status_code=422, content={"detail": "Invalid diagnostic request."})
    if request.url.path.startswith("/api/v1/work-orders"):
        return JSONResponse(status_code=422, content={"detail": "Check the work order fields."})
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    logger.exception("unexpected_request_failure")
    return JSONResponse(
        status_code=500, content={"detail": "An unexpected prediction service error occurred."}
    )


@app.get("/api/v1/health")
def health(request: Request):
    return {
        "status": "healthy",
        "models_loaded": hasattr(request.app.state, "models"),
        "service": "machineguard-api",
    }


@app.get("/api/v1/model/info")
def model_info(request: Request):
    return request.app.state.models.metadata


@app.get("/api/v1/machines/{machine_id}", response_model=MachineLookupResult)
def machine_lookup(machine_id: str, request: Request):
    if len(machine_id) > 64:
        raise HTTPException(400, "Machine ID is too long")
    try:
        return request.app.state.models.lookup(machine_id)
    except KeyError as exc:
        raise HTTPException(404, "Machine ID was not found in the asset database") from exc


@app.get("/api/v1/assets/summary", response_model=FleetSummary)
def asset_summary(request: Request):
    return request.app.state.models.fleet_summary()


@app.get("/api/v1/assets", response_model=AssetListResponse)
def asset_list(request: Request, category: str = "all", limit: int = 50, offset: int = 0):
    if not 1 <= limit <= 500 or offset < 0:
        raise HTTPException(400, "Limit must be 1–500 and offset cannot be negative")
    try:
        return request.app.state.models.list_assets(category, limit, offset)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/v1/assets", response_model=MachineLookupResult)
def save_asset(payload: MachineInput, request: Request):
    try:
        result = request.app.state.models.save(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    logger.info("asset_saved machine_id=%s", payload.machine_id)
    return result


@app.post("/api/v1/predict", response_model=PredictionResult)
def predict(payload: MachineInput, request: Request):
    result = request.app.state.models.predict(payload)
    logger.info("prediction_completed")
    return result


@app.post("/api/v1/predict/batch", response_model=BatchResponse)
async def predict_batch(request: Request, file: Annotated[UploadFile, File()]):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "CSV exceeds the 2 MB upload limit")
    try:
        frame = pd.read_csv(io.BytesIO(content))
        frame.columns = [str(column).strip().lower().replace(" ", "_") for column in frame.columns]
        if len(frame) > 5000:
            raise HTTPException(413, "CSV may contain at most 5,000 rows")
        items = [MachineInput.model_validate(row) for row in frame.to_dict(orient="records")]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Malformed CSV or invalid schema: {exc}") from exc
    results = request.app.state.models.predict_many(items)
    logger.info("batch_prediction_completed rows=%s", len(results))
    return {"count": len(results), "results": results}


app.include_router(knowledge_router)
app.include_router(diagnostic_router)
app.include_router(work_orders_router)

frontend_dist = settings.model_path.parents[2] / "frontend" / "dist"
if frontend_dist.exists():

    @app.get("/analysis", include_in_schema=False)
    @app.get("/batch", include_in_schema=False)
    @app.get("/knowledge", include_in_schema=False)
    @app.get("/diagnostics", include_in_schema=False)
    @app.get("/work-orders", include_in_schema=False)
    @app.get("/performance", include_in_schema=False)
    @app.get("/about", include_in_schema=False)
    def frontend_route():
        return FileResponse(frontend_dist / "index.html")

    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
