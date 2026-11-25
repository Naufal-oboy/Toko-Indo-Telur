"""Strictly read-only HTTP client for Express backend product catalog (BR-08)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from src.config import settings
from src.schemas import ProductItem

logger = logging.getLogger(__name__)


class BackendClientError(RuntimeError):
    """Raised when reading product data from Express backend fails."""


class BackendClient:
    """Read-only HTTP client calling GET /api/products on the Express backend."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.BACKEND_BASE_URL).rstrip("/")
        self.timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(settings.BACKEND_TIMEOUT_SECONDS)
        )

    def fetch_products(self) -> list[ProductItem]:
        """Fetch product list via read-only GET {BACKEND_BASE_URL}/api/products."""
        url = f"{self.base_url}/api/products"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("Backend product fetch timed out (%s): %s", url, exc)
            raise BackendClientError("Permintaan data produk ke backend timeout.") from exc
        except httpx.HTTPError as exc:
            logger.warning("Backend product fetch HTTP error (%s): %s", url, exc)
            raise BackendClientError("Gagal mengambil data produk dari backend.") from exc
        except ValueError as exc:
            logger.warning("Backend product fetch returned invalid JSON (%s): %s", url, exc)
            raise BackendClientError("Respons JSON dari backend tidak valid.") from exc

        return self._parse_envelope(payload)

    @staticmethod
    def _parse_envelope(payload: Any) -> list[ProductItem]:
        """Parse Express envelope { success, message, data: [...] }."""
        if not isinstance(payload, dict):
            raise BackendClientError("Format respons backend tidak valid (bukan objek JSON).")

        if payload.get("success") is not True:
            msg = payload.get("message") or "Backend mengembalikan status gagal."
            raise BackendClientError(str(msg))

        raw_items = payload.get("data")
        if not isinstance(raw_items, list):
            raise BackendClientError("Field 'data' pada respons backend harus berupa daftar.")

        products: list[ProductItem] = []
        for idx, row in enumerate(raw_items):
            try:
                products.append(ProductItem.model_validate(row))
            except Exception as exc:
                logger.warning("Skipping malformed product row at index %d: %s", idx, exc)
        return products


def load_sample_products(path: Path | str | None = None) -> list[ProductItem]:
    """Load local sample product catalog for offline/demo fallback."""
    catalog_path = Path(path) if path is not None else settings.SAMPLE_PRODUCTS_PATH
    if not catalog_path.exists():
        logger.warning("Sample products catalog not found at %s", catalog_path)
        return []

    try:
        raw_text = catalog_path.read_text(encoding="utf-8")
        raw_data = json.loads(raw_text)
        if isinstance(raw_data, dict) and isinstance(raw_data.get("data"), list):
            raw_items = raw_data["data"]
        elif isinstance(raw_data, list):
            raw_items = raw_data
        else:
            logger.warning("Unexpected format in sample products file %s", catalog_path)
            return []

        return [ProductItem.model_validate(row) for row in raw_items]
    except Exception as exc:
        logger.warning("Failed to load sample products from %s: %s", catalog_path, exc)
        return []
