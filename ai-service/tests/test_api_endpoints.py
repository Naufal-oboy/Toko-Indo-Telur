"""API endpoint tests using FastAPI TestClient (TC-10, AI-04)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from src import main as main_module
from src.config import Settings
from src.generative_service import SlidingWindowRateLimiter


class TestHealthEndpoint:
    """Verify GET /ai/health envelope, model status, and zero secret leakage."""

    def test_health_returns_loaded_model_and_never_leaks_secret(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_secret = "SUPER-SECRET-GEMINI-KEY-DO-NOT-LEAK"
        monkeypatch.setattr(main_module.settings, "GEMINI_API_KEY", fake_secret)

        response = client.get("/ai/health")
        assert response.status_code == 200
        body = response.json()

        assert body["success"] is True
        assert isinstance(body["message"], str) and body["message"]
        data = body["data"]
        assert data["status"] == "ok"
        assert data["model_loaded"] is True
        assert isinstance(data["model_name"], str) and data["model_name"]
        assert data["gemini_configured"] is True
        assert data["backend_configured"] is True
        assert data["api_key_auth_enabled"] is False
        assert "backend_base_url" not in data
        assert fake_secret not in response.text
        assert "GEMINI_API_KEY" not in data

    def test_optional_api_key_auth_blocks_unauthenticated_post_when_enabled(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(main_module.settings, "AI_SERVICE_API_KEY", "secret-service-token")

        health = client.get("/ai/health")
        assert health.status_code == 200
        assert health.json()["data"]["api_key_auth_enabled"] is True

        no_key = client.post("/ai/predict-intent", json={"message": "halo"})
        assert no_key.status_code == 401
        assert no_key.json()["success"] is False

        wrong_key = client.post(
            "/ai/predict-intent",
            json={"message": "halo"},
            headers={"X-API-Key": "wrong-token"},
        )
        assert wrong_key.status_code == 401

        ok_key = client.post(
            "/ai/predict-intent",
            json={"message": "halo"},
            headers={"X-API-Key": "secret-service-token"},
        )
        assert ok_key.status_code == 200
        assert ok_key.json()["success"] is True


class TestPredictIntentEndpoint:
    """Verify POST /ai/predict-intent valid and invalid inputs."""

    def test_predict_intent_valid_input(self, client: TestClient) -> None:
        response = client.post("/ai/predict-intent", json={"message": "stok telor ada?"})
        assert response.status_code == 200
        body = response.json()

        assert body["success"] is True
        data = body["data"]
        assert data["original_message"] == "stok telor ada?"
        assert data["normalized_message"] == "stok telur ada"
        assert data["intent"] == "cek_stok"
        assert 0.0 <= data["confidence"] <= 1.0
        assert set(data["scores"].keys()) == {
            "sapaan",
            "format_pesanan",
            "cek_stok",
            "cek_harga",
            "lainnya",
        }

    @pytest.mark.parametrize(
        "invalid_payload",
        [
            {"message": ""},
            {"message": "    \t\n  "},
            {},
            {"message": 12345},
            {"message": None},
            {"message": ["stok telur"]},
        ],
    )
    def test_predict_intent_invalid_inputs_return_express_error_envelope(
        self,
        client: TestClient,
        invalid_payload: dict[str, Any],
    ) -> None:
        response = client.post("/ai/predict-intent", json=invalid_payload)
        assert response.status_code == 422
        body = response.json()

        assert body["success"] is False
        assert isinstance(body["message"], str) and body["message"]
        assert body["data"] is None


class TestSuggestReplyEndpoint:
    """Verify POST /ai/suggest-reply validation, Gemini happy path, guardrails, and fallbacks."""

    def test_suggest_reply_valid_rule_mode(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
    ) -> None:
        response = client.post(
            "/ai/suggest-reply",
            json={
                "message": "harga gulaa berapa?",
                "intent": "cek_harga",
                "products": sample_products_raw,
                "use_generative": False,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["intent"] == "cek_harga"
        assert data["source"] == "fallback_rule"
        assert data["fallback_used"] is False
        assert data["query_status"] == "matched"
        assert data["matched_product"]["name"] == "Gula Pasir 1 kg"
        assert "Rp17.500" in data["reply"]
        assert data["disclaimer_included"] is True

    @pytest.mark.parametrize(
        "invalid_payload",
        [
            {"message": "", "intent": "sapaan"},
            {"message": "   ", "intent": "sapaan"},
            {"message": "halo"},
            {"message": "halo", "intent": "intent_tidak_valid"},
        ],
    )
    def test_suggest_reply_invalid_inputs_return_express_error_envelope(
        self,
        client: TestClient,
        invalid_payload: dict[str, Any],
    ) -> None:
        response = client.post("/ai/suggest-reply", json=invalid_payload)
        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert isinstance(body["message"], str) and body["message"]
        assert body["data"] is None

    def test_suggest_reply_simulate_failure_triggers_safe_fallback(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
    ) -> None:
        response = client.post(
            "/ai/suggest-reply",
            json={
                "message": "stok telor ada?",
                "intent": "cek_stok",
                "products": sample_products_raw,
                "use_generative": True,
                "simulate_failure": True,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["source"] == "fallback_rule"
        assert data["fallback_used"] is True
        assert data["fallback_reason"] == "simulated_failure"
        assert data["matched_product"]["name"] == "Telur Ayam Ras 1 Rak"
        assert "perkiraan" in data["reply"].lower()

    def test_suggest_reply_mocked_gemini_happy_path(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        test_settings = Settings(
            GEMINI_API_KEY="fake-test-key",
            GEMINI_MAX_CALLS_PER_MINUTE=10,
            GEMINI_TIMEOUT_SECONDS=5.0,
        )
        monkeypatch.setattr(main_module.generative_service, "settings", test_settings)
        monkeypatch.setattr(
            main_module.generative_service,
            "rate_limiter",
            SlidingWindowRateLimiter(max_calls=10, window_seconds=60.0),
        )
        expected_reply = (
            "Harga Gula Pasir 1 kg saat ini Rp17.500/kg dengan status stok tersedia. "
            "Sebagai catatan, stok bersifat perkiraan dan mohon konfirmasi ke pemilik toko."
        )
        monkeypatch.setattr(
            main_module.generative_service,
            "_invoke_gemini",
            lambda _prompt: expected_reply,
        )

        response = client.post(
            "/ai/suggest-reply",
            json={
                "message": "harga gula berapa?",
                "intent": "cek_harga",
                "products": sample_products_raw,
                "use_generative": True,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["source"] == "gemini"
        assert data["fallback_used"] is False
        assert data["fallback_reason"] is None
        assert data["reply"] == expected_reply
        assert data["disclaimer_included"] is True

    @pytest.mark.parametrize(
        "canonical_price_reply",
        [
            "Harga Gula Pasir 1 kg adalah Rp 17.500,00/kg, status stok tersedia (perkiraan, konfirmasi pemilik).",
            "Harga Gula Pasir 1 kg adalah Rp17,500/kg, status stok tersedia (perkiraan, konfirmasi pemilik).",
            "Harga Gula Pasir 1 kg adalah Rp17500/kg, status stok tersedia (perkiraan, konfirmasi pemilik).",
        ],
    )
    def test_suggest_reply_accepts_canonical_rupiah_formats_without_false_rejection(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
        canonical_price_reply: str,
    ) -> None:
        test_settings = Settings(GEMINI_API_KEY="fake-test-key")
        monkeypatch.setattr(main_module.generative_service, "settings", test_settings)
        monkeypatch.setattr(
            main_module.generative_service,
            "rate_limiter",
            SlidingWindowRateLimiter(max_calls=10, window_seconds=60.0),
        )
        monkeypatch.setattr(
            main_module.generative_service,
            "_invoke_gemini",
            lambda _prompt: canonical_price_reply,
        )

        response = client.post(
            "/ai/suggest-reply",
            json={
                "message": "harga gula berapa?",
                "intent": "cek_harga",
                "products": sample_products_raw,
                "use_generative": True,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["source"] == "gemini"
        assert data["fallback_used"] is False

    def test_suggest_reply_guards_against_extended_hallucinations(
        self,
        sample_products: list[Any],
    ) -> None:
        from src.generative_service import validate_generated_reply
        from src.product_matcher import match_product

        matched_gula = match_product("harga gula berapa?", sample_products).matched_product
        matched_susu = match_product("stok susu kental manis ada?", sample_products).matched_product
        assert matched_gula is not None and matched_susu is not None

        # Wrong product name
        ok, reason = validate_generated_reply(
            "Harga Beras Premium Rp17.500/kg, status stok tersedia (perkiraan).",
            intent="cek_harga",
            query_status="matched",
            matched_product=matched_gula,
            auto_reply_stock_enabled=True,
        )
        assert not ok and reason == "missing_verified_product_name"

        # Hallucinated price in cek_stok
        ok, reason = validate_generated_reply(
            "Stok Gula Pasir 1 kg tersedia (perkiraan 40 kg) dengan harga Rp5.000/kg.",
            intent="cek_stok",
            query_status="matched",
            matched_product=matched_gula,
            auto_reply_stock_enabled=True,
        )
        assert not ok and reason == "hallucinated_price_in_stock_reply"

        # Contradicting stock status on habis product
        ok, reason = validate_generated_reply(
            "Stok Susu Kental Manis Kaleng masih tersedia 100 kaleng, belum habis (perkiraan).",
            intent="cek_stok",
            query_status="matched",
            matched_product=matched_susu,
            auto_reply_stock_enabled=True,
        )
        assert not ok and reason == "contradicting_stock_status"

        # Fabricated 'rupiah' without Rp prefix on not_found
        ok, reason = validate_generated_reply(
            "Maaf emas tidak ada, biasanya sekitar 500.000 rupiah per gram.",
            intent="cek_harga",
            query_status="not_found",
            matched_product=None,
            auto_reply_stock_enabled=True,
        )
        assert not ok and reason == "fabricated_price_for_unknown_product"

        # Fabricated price / booking in sapaan
        ok, reason = validate_generated_reply(
            "Halo! Hari ini telur promo Rp10.000/rak ya kak.",
            intent="sapaan",
            query_status="not_applicable",
            matched_product=None,
            auto_reply_stock_enabled=True,
        )
        assert not ok and reason == "fabricated_price_in_non_price_intent"

        # Missing required order format fields in format_pesanan
        ok, reason = validate_generated_reply(
            "Oke silakan chat saja nanti saya bantu proses pesanannya ya kak!",
            intent="format_pesanan",
            query_status="not_applicable",
            matched_product=None,
            auto_reply_stock_enabled=True,
        )
        assert not ok and reason == "missing_required_order_format_fields"

    @pytest.mark.parametrize(
        ("bad_gemini_reply", "expected_reason_fragment"),
        [
            (
                "Harga Gula Pasir 1 kg cuma Rp9.999/kg, stok tersedia (perkiraan).",
                "missing_exact_verified_price",
            ),
            (
                "Harga Gula Pasir 1 kg Rp17.500/kg, status stok tersedia sekarang.",
                "missing_stock_estimate_disclaimer",
            ),
            (
                "Harga Gula Pasir 1 kg Rp17.500/kg, stok tersedia (perkiraan), stok sudah dikurangi untuk Anda.",
                "forbidden_stock_mutation_claim",
            ),
        ],
    )
    def test_suggest_reply_factuality_guard_violation_triggers_fallback(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
        bad_gemini_reply: str,
        expected_reason_fragment: str,
    ) -> None:
        test_settings = Settings(
            GEMINI_API_KEY="fake-test-key",
            GEMINI_MAX_CALLS_PER_MINUTE=10,
            GEMINI_TIMEOUT_SECONDS=5.0,
        )
        monkeypatch.setattr(main_module.generative_service, "settings", test_settings)
        monkeypatch.setattr(
            main_module.generative_service,
            "rate_limiter",
            SlidingWindowRateLimiter(max_calls=10, window_seconds=60.0),
        )
        monkeypatch.setattr(
            main_module.generative_service,
            "_invoke_gemini",
            lambda _prompt: bad_gemini_reply,
        )

        response = client.post(
            "/ai/suggest-reply",
            json={
                "message": "harga gula berapa?",
                "intent": "cek_harga",
                "products": sample_products_raw,
                "use_generative": True,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["source"] == "fallback_rule"
        assert data["fallback_used"] is True
        assert data["fallback_reason"] == f"factuality_guard_failed:{expected_reason_fragment}"
        assert "Rp17.500" in data["reply"]
        assert "perkiraan" in data["reply"].lower()

    def test_suggest_reply_rate_limit_exceeded_triggers_fallback(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        test_settings = Settings(
            GEMINI_API_KEY="fake-test-key",
            GEMINI_MAX_CALLS_PER_MINUTE=1,
            GEMINI_TIMEOUT_SECONDS=5.0,
        )
        monkeypatch.setattr(main_module.generative_service, "settings", test_settings)
        monkeypatch.setattr(
            main_module.generative_service,
            "rate_limiter",
            SlidingWindowRateLimiter(max_calls=1, window_seconds=60.0),
        )
        monkeypatch.setattr(
            main_module.generative_service,
            "_invoke_gemini",
            lambda _prompt: "Halo Kak! Selamat datang di Toko Indo Telur, ada yang bisa kami bantu?",
        )

        # First call consumes the 1 allowed call in the window
        first = client.post(
            "/ai/suggest-reply",
            json={"message": "halo", "intent": "sapaan", "use_generative": True},
        )
        assert first.status_code == 200
        assert first.json()["data"]["source"] == "gemini"
        assert first.json()["data"]["fallback_used"] is False

        # Second call exceeds rate cap and falls back cleanly
        second = client.post(
            "/ai/suggest-reply",
            json={"message": "halo", "intent": "sapaan", "use_generative": True},
        )
        assert second.status_code == 200
        second_data = second.json()["data"]
        assert second_data["source"] == "fallback_rule"
        assert second_data["fallback_used"] is True
        assert second_data["fallback_reason"] == "rate_limit_exceeded"


class TestChatbotRespondEndpoint:
    """Verify POST /ai/chatbot/respond across payload, mocked backend GET, and sample fallback."""

    def test_chatbot_respond_with_payload_products(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
    ) -> None:
        response = client.post(
            "/ai/chatbot/respond",
            json={
                "message": "stok telor ada?",
                "sender_id": "test-user-01",
                "channel": "simulator",
                "products": sample_products_raw,
                "use_generative": False,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["intent"] == "cek_stok"
        assert data["data_source"] == "request_payload"
        assert data["query_status"] == "matched"
        assert data["matched_product"]["name"] == "Telur Ayam Ras 1 Rak"
        assert data["disclaimer_included"] is True

    def test_chatbot_respond_with_mocked_backend_get_products(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        backend_catalog = [
            {
                "id": 101,
                "sku": "GUL-SRV",
                "name": "Gula Pasir Server 1 kg",
                "price": "18250.00",
                "stock": "12.000",
                "unit": "kg",
                "is_active": True,
            }
        ]

        class _FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, Any]:
                return {
                    "success": True,
                    "message": "Products retrieved",
                    "data": backend_catalog,
                }

        captured_urls: list[str] = []

        def _fake_get(self: httpx.Client, url: str, *args: Any, **kwargs: Any) -> _FakeResponse:
            captured_urls.append(str(url))
            return _FakeResponse()

        monkeypatch.setattr(httpx.Client, "get", _fake_get)

        response = client.post(
            "/ai/chatbot/respond",
            json={
                "message": "harga gula berapa?",
                "channel": "whatsapp_test",
                "products": None,
                "use_generative": False,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["intent"] == "cek_harga"
        assert data["data_source"] == "backend_api"
        assert data["matched_product"]["name"] == "Gula Pasir Server 1 kg"
        assert "Rp18.250" in data["reply"]
        assert any(url.endswith("/api/products") for url in captured_urls)

    def test_chatbot_respond_falls_back_to_sample_catalog_when_backend_unavailable(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _failing_get(self: httpx.Client, url: str, *args: Any, **kwargs: Any) -> Any:
            raise httpx.ConnectError("Backend offline")

        monkeypatch.setattr(httpx.Client, "get", _failing_get)
        monkeypatch.setattr(main_module.orchestrator.settings, "USE_SAMPLE_PRODUCTS_FALLBACK", True)

        response = client.post(
            "/ai/chatbot/respond",
            json={
                "message": "harga gulaa berapa?",
                "channel": "simulator",
                "products": None,
                "use_generative": False,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["intent"] == "cek_harga"
        assert data["data_source"] == "sample_catalog"
        assert data["query_status"] == "matched"
        assert data["matched_product"]["name"] == "Gula Pasir 1 kg"
        assert "Rp17.500" in data["reply"]

    def test_chatbot_respond_returns_catalog_unavailable_when_backend_down_and_fallback_off(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _failing_get(self: httpx.Client, url: str, *args: Any, **kwargs: Any) -> Any:
            raise httpx.ConnectError("Backend offline")

        monkeypatch.setattr(httpx.Client, "get", _failing_get)
        monkeypatch.setattr(main_module.orchestrator.settings, "USE_SAMPLE_PRODUCTS_FALLBACK", False)

        response = client.post(
            "/ai/chatbot/respond",
            json={
                "message": "harga gula berapa?",
                "products": None,
                "use_generative": False,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["data_source"] == "none"
        assert data["query_status"] == "catalog_unavailable"
        assert data["matched_product"] is None
        assert "tidak tersedia" in data["reply"].lower()
        assert "belum ditemukan" not in data["reply"].lower()
