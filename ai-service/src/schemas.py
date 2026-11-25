"""Pydantic request and response schemas for Toko Indo Telur AI Service."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

VALID_INTENTS = (
    "sapaan",
    "format_pesanan",
    "cek_stok",
    "cek_harga",
    "lainnya",
)

IntentLabel = Literal[
    "sapaan",
    "format_pesanan",
    "cek_stok",
    "cek_harga",
    "lainnya",
]
StockStatus = Literal["tersedia", "menipis", "habis"]
QueryStatus = Literal[
    "matched",
    "not_found",
    "missing_product_name",
    "catalog_unavailable",
    "not_applicable",
]
ReplySource = Literal["gemini", "fallback_rule"]
DataSource = Literal[
    "request_payload",
    "backend_api",
    "sample_catalog",
    "none",
]


def _validate_non_empty_message(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Pesan wajib berupa teks.")
    if not value.strip():
        raise ValueError("Pesan tidak boleh kosong atau hanya spasi.")
    if len(value) > 2000:
        raise ValueError("Pesan maksimal 2000 karakter.")
    return value


def _parse_numeric(value: Any, field_label: str, *, allow_none: bool = False) -> float:
    if value is None:
        if allow_none:
            return 0.0
        raise ValueError(f"{field_label} wajib diisi.")
    if isinstance(value, bool):
        raise ValueError(f"{field_label} harus berupa angka.")
    if isinstance(value, (int, float, Decimal)):
        parsed = float(value)
    elif isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{field_label} tidak boleh kosong.")
        try:
            parsed = float(cleaned)
        except ValueError as exc:
            raise ValueError(f"{field_label} harus berupa angka yang valid.") from exc
    else:
        raise ValueError(f"{field_label} harus berupa angka.")

    if math.isnan(parsed) or math.isinf(parsed):
        raise ValueError(f"{field_label} harus berupa angka terbatas.")
    if parsed < 0:
        raise ValueError(f"{field_label} tidak boleh bernilai negatif.")
    return parsed


class ApiEnvelope(BaseModel):
    """Consistent response envelope matching backend Express API."""

    success: bool
    message: str
    data: Any = None


class ProductItem(BaseModel):
    """Product representation aligned with Express GET /api/products."""

    model_config = ConfigDict(extra="ignore")

    id: int | str | None = None
    sku: str | None = None
    name: str = Field(..., min_length=1)
    description: str | None = None
    price: float
    stock: float = 0.0
    unit: str = "pcs"
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nama produk tidak boleh kosong.")
        return cleaned

    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, value: Any) -> float:
        return _parse_numeric(value, "Harga produk", allow_none=False)

    @field_validator("stock", mode="before")
    @classmethod
    def validate_stock(cls, value: Any) -> float:
        return _parse_numeric(value, "Stok produk", allow_none=True)

    @field_validator("unit", mode="before")
    @classmethod
    def validate_unit(cls, value: Any) -> str:
        if value is None:
            return "pcs"
        cleaned = str(value).strip()
        return cleaned or "pcs"


class MatchedProductInfo(BaseModel):
    """Verified product metadata returned when a catalog item is matched."""

    id: int | str | None = None
    sku: str | None = None
    name: str
    price: float
    formatted_price: str
    stock: float
    unit: str
    stock_status: StockStatus
    match_score: float
    is_active: bool = True


class PredictIntentRequest(BaseModel):
    """Request body for POST /ai/predict-intent."""

    message: StrictStr

    @field_validator("message")
    @classmethod
    def check_message(cls, value: str) -> str:
        return _validate_non_empty_message(value)


class PredictIntentData(BaseModel):
    """Response payload data for POST /ai/predict-intent."""

    original_message: str
    normalized_message: str
    intent: IntentLabel
    confidence: float
    scores: dict[str, float]


class SuggestReplyRequest(BaseModel):
    """Request body for POST /ai/suggest-reply."""

    message: StrictStr
    intent: IntentLabel
    products: list[ProductItem] | None = None
    use_generative: bool = True
    auto_reply_stock_enabled: bool | None = None
    simulate_failure: bool = False

    @field_validator("message")
    @classmethod
    def check_message(cls, value: str) -> str:
        return _validate_non_empty_message(value)


class SuggestReplyData(BaseModel):
    """Response payload data for POST /ai/suggest-reply."""

    intent: IntentLabel
    reply: str
    source: ReplySource
    fallback_used: bool
    fallback_reason: str | None = None
    query_status: QueryStatus
    matched_product: MatchedProductInfo | None = None
    auto_reply_stock_enabled: bool
    disclaimer_included: bool


class ChatbotRespondRequest(BaseModel):
    """Request body for POST /ai/chatbot/respond."""

    message: StrictStr
    sender_id: str | None = None
    channel: str = "simulator"
    products: list[ProductItem] | None = None
    use_generative: bool = True
    auto_reply_stock_enabled: bool | None = None
    simulate_failure: bool = False

    @field_validator("message")
    @classmethod
    def check_message(cls, value: str) -> str:
        return _validate_non_empty_message(value)

    @field_validator("channel", mode="before")
    @classmethod
    def normalize_channel(cls, value: Any) -> str:
        if value is None:
            return "simulator"
        cleaned = str(value).strip()
        return cleaned or "simulator"


class ChatbotRespondData(BaseModel):
    """Response payload data for POST /ai/chatbot/respond."""

    sender_id: str | None = None
    channel: str
    original_message: str
    normalized_message: str
    intent: IntentLabel
    confidence: float
    scores: dict[str, float]
    reply: str
    source: ReplySource
    fallback_used: bool
    fallback_reason: str | None = None
    query_status: QueryStatus
    matched_product: MatchedProductInfo | None = None
    auto_reply_stock_enabled: bool
    disclaimer_included: bool
    data_source: DataSource


class HealthData(BaseModel):
    """Response payload data for GET /ai/health."""

    status: str
    service: str
    model_loaded: bool
    model_name: str | None = None
    gemini_configured: bool
    gemini_model: str
    auto_reply_stock_enabled: bool
    low_stock_threshold: float
    backend_configured: bool
    api_key_auth_enabled: bool
