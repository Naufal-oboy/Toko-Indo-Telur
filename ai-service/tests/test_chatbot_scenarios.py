"""End-to-end chatbot acceptance scenarios (TC-07, TC-08, BR-08, Risiko #3)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from src.backend_client import BackendClient


class TestBasicChatScenariosTC07:
    """Verify greeting, order format, and unknown/random message handling (TC-07)."""

    def test_greeting_halo_returns_polite_greeting(self, client: TestClient) -> None:
        response = client.post(
            "/ai/chatbot/respond",
            json={"message": "halo", "use_generative": False},
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["intent"] == "sapaan"
        assert data["query_status"] == "not_applicable"
        assert "halo" in data["reply"].lower()
        assert "toko indo telur" in data["reply"].lower()

    def test_order_intent_mau_pesan_returns_format_instructions(
        self,
        client: TestClient,
    ) -> None:
        response = client.post(
            "/ai/chatbot/respond",
            json={"message": "mau pesan", "use_generative": False},
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["intent"] == "format_pesanan"
        assert data["query_status"] == "not_applicable"
        reply_lower = data["reply"].lower()
        assert "format" in reply_lower
        assert "barang" in reply_lower and "jumlah" in reply_lower

    @pytest.mark.parametrize(
        "message",
        [
            "asdfghjkl 12345 xyz",
            "komplain barang kemarin pecah",
        ],
    )
    def test_random_or_out_of_scope_message_returns_polite_guidance(
        self,
        client: TestClient,
        message: str,
    ) -> None:
        response = client.post(
            "/ai/chatbot/respond",
            json={"message": message, "use_generative": False},
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["intent"] == "lainnya"
        assert data["query_status"] == "not_applicable"
        reply_lower = data["reply"].lower()
        assert "pemilik" in reply_lower or "manual" in reply_lower


class TestStockAndPriceScenariosTC08:
    """Verify accurate server lookup, typo tolerance, disclaimer, and unknown products (TC-08)."""

    @pytest.mark.parametrize("message", ["stok telur ada?", "stok telor ada?"])
    def test_stock_inquiry_exact_and_typo_returns_server_data_with_disclaimer(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
        message: str,
    ) -> None:
        response = client.post(
            "/ai/chatbot/respond",
            json={
                "message": message,
                "products": sample_products_raw,
                "use_generative": False,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["intent"] == "cek_stok"
        assert data["query_status"] == "matched"
        assert data["matched_product"]["name"] == "Telur Ayam Ras 1 Rak"
        assert data["matched_product"]["stock_status"] == "tersedia"
        assert data["disclaimer_included"] is True
        assert "perkiraan" in data["reply"].lower()
        assert "tersedia" in data["reply"].lower()

    @pytest.mark.parametrize("message", ["harga gula berapa?", "harga gulaa berapa?"])
    def test_price_inquiry_exact_and_typo_returns_server_data_with_disclaimer(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
        message: str,
    ) -> None:
        response = client.post(
            "/ai/chatbot/respond",
            json={
                "message": message,
                "products": sample_products_raw,
                "use_generative": False,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["intent"] == "cek_harga"
        assert data["query_status"] == "matched"
        assert data["matched_product"]["name"] == "Gula Pasir 1 kg"
        assert data["matched_product"]["formatted_price"] == "Rp17.500"
        assert "Rp17.500" in data["reply"]
        assert data["disclaimer_included"] is True
        assert "perkiraan" in data["reply"].lower()

    def test_unknown_product_returns_polite_clear_response_without_fake_price(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
    ) -> None:
        response = client.post(
            "/ai/chatbot/respond",
            json={
                "message": "stok emas batangan ada?",
                "products": sample_products_raw,
                "use_generative": False,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["intent"] == "cek_stok"
        assert data["query_status"] == "not_found"
        assert data["matched_product"] is None
        reply_lower = data["reply"].lower()
        assert "belum ditemukan" in reply_lower or "maaf" in reply_lower
        assert "rp" not in reply_lower


class TestOperationalSafetyMitigations:
    """Verify Risiko #3 stock auto-reply toggle and BR-08 read-only backend client."""

    def test_auto_reply_stock_disabled_returns_manual_notice_without_stock_info(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
    ) -> None:
        response = client.post(
            "/ai/chatbot/respond",
            json={
                "message": "stok telur ada?",
                "products": sample_products_raw,
                "use_generative": True,
                "auto_reply_stock_enabled": False,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["intent"] == "cek_stok"
        assert data["auto_reply_stock_enabled"] is False
        assert data["fallback_reason"] == "auto_reply_stock_disabled"
        assert data["matched_product"] is None
        reply_lower = data["reply"].lower()
        assert "dinonaktifkan" in reply_lower
        assert "manual" in reply_lower
        assert "tersedia" not in reply_lower
        assert "24" not in reply_lower

    def test_auto_reply_stock_disabled_hides_stock_on_cek_harga_too(
        self,
        client: TestClient,
        sample_products_raw: list[dict[str, Any]],
    ) -> None:
        response = client.post(
            "/ai/chatbot/respond",
            json={
                "message": "harga gulaa berapa?",
                "products": sample_products_raw,
                "use_generative": False,
                "auto_reply_stock_enabled": False,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["intent"] == "cek_harga"
        assert data["auto_reply_stock_enabled"] is False
        assert data["query_status"] == "matched"
        assert "Rp17.500" in data["reply"]
        reply_lower = data["reply"].lower()
        assert "tersedia" not in reply_lower
        assert "menipis" not in reply_lower
        assert "habis" not in reply_lower
        assert "manual" in reply_lower

    def test_backend_client_is_strictly_read_only_http_get(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # 1. Verify no mutating helper methods exist on BackendClient
        public_methods = [
            name for name in dir(BackendClient) if not name.startswith("_")
        ]
        for forbidden in ("post", "put", "patch", "delete", "update", "create", "mutate"):
            assert all(forbidden not in method.lower() for method in public_methods)

        # 2. Verify runtime HTTP calls strictly use GET and never POST/PUT/DELETE/PATCH
        recorded_methods: list[tuple[str, str]] = []

        class _ReadOnlySpyClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def __enter__(self) -> _ReadOnlySpyClient:
                return self

            def __exit__(self, *args: Any) -> None:
                return None

            def get(self, url: str, *args: Any, **kwargs: Any) -> Any:
                recorded_methods.append(("GET", str(url)))

                class _Resp:
                    def raise_for_status(self) -> None:
                        return None

                    def json(self) -> dict[str, Any]:
                        return {
                            "success": True,
                            "message": "OK",
                            "data": [
                                {
                                    "id": 1,
                                    "sku": "TLR-RAK30",
                                    "name": "Telur Ayam Ras 1 Rak",
                                    "price": "58000.00",
                                    "stock": "24.000",
                                    "unit": "rak",
                                    "is_active": True,
                                }
                            ],
                        }

                return _Resp()

            def post(self, *args: Any, **kwargs: Any) -> Any:
                raise AssertionError("BR-08 violation: BackendClient must never invoke HTTP POST")

            def put(self, *args: Any, **kwargs: Any) -> Any:
                raise AssertionError("BR-08 violation: BackendClient must never invoke HTTP PUT")

            def patch(self, *args: Any, **kwargs: Any) -> Any:
                raise AssertionError("BR-08 violation: BackendClient must never invoke HTTP PATCH")

            def delete(self, *args: Any, **kwargs: Any) -> Any:
                raise AssertionError("BR-08 violation: BackendClient must never invoke HTTP DELETE")

            def request(self, method: str, *args: Any, **kwargs: Any) -> Any:
                raise AssertionError(
                    f"BR-08 violation: Unexpected httpx.Client.request({method})"
                )

        monkeypatch.setattr(httpx, "Client", _ReadOnlySpyClient)

        backend = BackendClient(base_url="http://backend.local:3000", timeout_seconds=3.0)
        products = backend.fetch_products()

        assert len(products) == 1
        assert products[0].sku == "TLR-RAK30"
        assert recorded_methods == [("GET", "http://backend.local:3000/api/products")]
