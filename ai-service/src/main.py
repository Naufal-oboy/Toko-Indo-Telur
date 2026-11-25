"""FastAPI application for Toko Indo Telur AI Service."""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.backend_client import BackendClient
from src.chatbot_orchestrator import ChatbotOrchestrator
from src.config import settings
from src.generative_service import GenerativeReplyService
from src.intent_service import IntentService, ModelNotLoadedError
from src.schemas import (
    ApiEnvelope,
    ChatbotRespondRequest,
    HealthData,
    PredictIntentData,
    PredictIntentRequest,
    SuggestReplyRequest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

intent_service = IntentService(model_path=settings.MODEL_PATH)
backend_client = BackendClient(
    base_url=settings.BACKEND_BASE_URL,
    timeout_seconds=settings.BACKEND_TIMEOUT_SECONDS,
)
generative_service = GenerativeReplyService(app_settings=settings)
orchestrator = ChatbotOrchestrator(
    intent_service=intent_service,
    backend_client=backend_client,
    generative_service=generative_service,
    app_settings=settings,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load the trained intent model at application startup."""
    intent_service.load()
    yield


app = FastAPI(
    title="Toko Indo Telur AI Service",
    description=(
        "REST API klasifikasi intent, pencocokan produk read-only, dan saran balasan "
        "chatbot WhatsApp untuk Toko Indo Telur (A26-CS201)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "data": None,
        },
    )


def _format_validation_error(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Input request tidak valid."
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    msg = str(first.get("msg", "Input tidak valid."))
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, ") :]
    return f"{loc}: {msg}" if loc else msg


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return _error_response(422, _format_validation_error(exc))


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    _request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return _error_response(exc.status_code, str(exc.detail))


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return _error_response(400, str(exc))


@app.exception_handler(ModelNotLoadedError)
async def model_not_loaded_handler(
    _request: Request,
    exc: ModelNotLoadedError,
) -> JSONResponse:
    return _error_response(503, str(exc))


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error in AI service: %s", exc)
    return _error_response(500, "Terjadi kesalahan pada server AI.")


def _verify_optional_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Require X-API-Key only when AI_SERVICE_API_KEY is configured."""
    if not settings.api_key_auth_enabled:
        return
    expected = settings.AI_SERVICE_API_KEY.strip()
    if not x_api_key or not hmac.compare_digest(x_api_key.strip(), expected):
        raise StarletteHTTPException(
            status_code=401,
            detail="API key layanan AI tidak valid atau tidak disertakan.",
        )


@app.get("/ai/health", response_model=ApiEnvelope)
def ai_health() -> dict[str, Any]:
    """Return service health, loaded intent model status, and non-secret config status."""
    health = HealthData(
        status="ok",
        service="toko-indo-telur-ai-service",
        model_loaded=intent_service.is_loaded,
        model_name=intent_service.model_name,
        gemini_configured=settings.gemini_configured,
        gemini_model=settings.GEMINI_MODEL,
        auto_reply_stock_enabled=settings.AUTO_REPLY_STOCK_ENABLED,
        low_stock_threshold=settings.LOW_STOCK_THRESHOLD,
        backend_configured=settings.backend_configured,
        api_key_auth_enabled=settings.api_key_auth_enabled,
    )
    return {
        "success": True,
        "message": "Toko Indo Telur AI Service berjalan",
        "data": health.model_dump(),
    }


@app.post(
    "/ai/predict-intent",
    response_model=ApiEnvelope,
    dependencies=[Depends(_verify_optional_api_key)],
)
def predict_intent(payload: PredictIntentRequest) -> dict[str, Any]:
    """Classify customer chat intent and return probability distribution."""
    result = intent_service.predict(payload.message)
    data = PredictIntentData.model_validate(result)
    return {
        "success": True,
        "message": "Prediksi intent berhasil",
        "data": data.model_dump(),
    }


@app.post(
    "/ai/suggest-reply",
    response_model=ApiEnvelope,
    dependencies=[Depends(_verify_optional_api_key)],
)
def suggest_reply(payload: SuggestReplyRequest) -> dict[str, Any]:
    """Generate a factuality-checked reply suggestion or deterministic fallback."""
    data = orchestrator.suggest_reply(payload)
    return {
        "success": True,
        "message": "Saran balasan berhasil dibuat",
        "data": data.model_dump(),
    }


@app.post(
    "/ai/chatbot/respond",
    response_model=ApiEnvelope,
    dependencies=[Depends(_verify_optional_api_key)],
)
def chatbot_respond(payload: ChatbotRespondRequest) -> dict[str, Any]:
    """End-to-end chatbot endpoint for simulator and WhatsApp webhook integration."""
    data = orchestrator.respond(payload)
    return {
        "success": True,
        "message": "Respons chatbot berhasil dibuat",
        "data": data.model_dump(),
    }
