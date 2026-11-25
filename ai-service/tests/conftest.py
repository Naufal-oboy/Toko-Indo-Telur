"""Shared pytest fixtures and path setup for Toko Indo Telur AI Service tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

AI_SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from src import main as main_module  # noqa: E402
from src.schemas import ProductItem  # noqa: E402


@pytest.fixture(scope="session")
def ai_service_root() -> Path:
    """Return absolute path to the ai-service directory."""
    return AI_SERVICE_ROOT


@pytest.fixture(scope="session")
def sample_products_raw(ai_service_root: Path) -> list[dict[str, Any]]:
    """Load raw sample catalog JSON matching Express GET /api/products."""
    sample_path = ai_service_root / "data" / "sample_products.json"
    return json.loads(sample_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def sample_products(sample_products_raw: list[dict[str, Any]]) -> list[ProductItem]:
    """Return parsed ProductItem list from data/sample_products.json."""
    return [ProductItem.model_validate(item) for item in sample_products_raw]


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """FastAPI TestClient with lifespan enabled, isolated from local .env keys."""
    monkeypatch.setattr(main_module.settings, "GEMINI_API_KEY", "")
    main_module.generative_service.reset_rate_limiter()
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.generative_service.reset_rate_limiter()
