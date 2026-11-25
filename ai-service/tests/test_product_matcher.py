"""Tests for active-only, typo-tolerant product matching and stock thresholds (TC-08)."""

from __future__ import annotations

import pytest

from src.product_matcher import (
    compute_stock_status,
    format_rupiah,
    format_stock_quantity,
    match_product,
)
from src.schemas import ProductItem


class TestProductMatching:
    """Verify exact/typo matching, inactive filtering, and query status distinctions."""

    @pytest.mark.parametrize(
        ("query", "expected_sku", "expected_name"),
        [
            ("stok telur ada?", "TLR-RAK30", "Telur Ayam Ras 1 Rak"),
            ("stok telor ada?", "TLR-RAK30", "Telur Ayam Ras 1 Rak"),
            ("harga gula berapa?", "GUL-1KG", "Gula Pasir 1 kg"),
            ("harga gulaa berapa?", "GUL-1KG", "Gula Pasir 1 kg"),
            ("migor 2 liter ready ga?", "MGR-2L", "Minyak Goreng 2 Liter"),
            ("harga beras 5kg brp?", "BRS-5KG", "Beras Medium 5 kg"),
            ("migor 2 liter stoknya masih ada?", "MGR-2L", "Minyak Goreng 2 Liter"),
            ("gula pasir 1 kg harganya brp ya?", "GUL-1KG", "Gula Pasir 1 kg"),
            ("stok beras masih aman gak kak?", "BRS-5KG", "Beras Medium 5 kg"),
            ("cek ketersediaan stok tepung terigu", "TPG-1KG", "Tepung Terigu 1 kg"),
            ("telurnya masih ada kak?", "TLR-RAK30", "Telur Ayam Ras 1 Rak"),
        ],
    )
    def test_matches_exact_and_typo_queries(
        self,
        sample_products: list[ProductItem],
        query: str,
        expected_sku: str,
        expected_name: str,
    ) -> None:
        result = match_product(query, sample_products)

        assert result.query_status == "matched"
        assert result.matched_product is not None
        assert result.matched_product.sku == expected_sku
        assert result.matched_product.name == expected_name
        assert result.matched_product.is_active is True

    def test_strictly_ignores_inactive_products(
        self,
        sample_products: list[ProductItem],
    ) -> None:
        # "Sirup Melon Musiman 600 ml" (SKU: SRP-MLN600) has is_active=False in sample_products.json
        by_name = match_product("stok sirup melon musiman ada?", sample_products)
        assert by_name.query_status == "not_found"
        assert by_name.matched_product is None
        assert by_name.active_product_count == 10

        by_sku = match_product("harga SRP-MLN600 berapa?", sample_products)
        assert by_sku.query_status == "not_found"
        assert by_sku.matched_product is None

        # Even when an inactive item is the ONLY catalog entry, it must never match
        inactive_only = [
            ProductItem(
                id=99,
                sku="INACT-01",
                name="Telur Kampung Khusus",
                price=65000.0,
                stock=10.0,
                unit="rak",
                is_active=False,
            )
        ]
        result = match_product("stok telur kampung khusus ada?", inactive_only)
        assert result.query_status == "not_found"
        assert result.matched_product is None
        assert result.active_product_count == 0

    @pytest.mark.parametrize(
        "query",
        [
            "stok ada?",
            "harga berapa?",
            "cek stok dong kak",
            "info harga hari ini berapa ya?",
        ],
    )
    def test_distinguishes_missing_product_name(
        self,
        sample_products: list[ProductItem],
        query: str,
    ) -> None:
        result = match_product(query, sample_products)
        assert result.query_status == "missing_product_name"
        assert result.matched_product is None

    @pytest.mark.parametrize(
        "query",
        [
            "stok emas batangan ada?",
            "harga kulkas dua pintu berapa?",
            "stok laptop gaming ready?",
            "harga beras premium berapa?",
        ],
    )
    def test_distinguishes_unknown_product_as_not_found(
        self,
        sample_products: list[ProductItem],
        query: str,
    ) -> None:
        result = match_product(query, sample_products)
        assert result.query_status == "not_found"
        assert result.matched_product is None

    def test_preserves_decimal_sizes_and_disambiguates_package_variants(self) -> None:
        from src.product_matcher import extract_product_query_tokens

        all_tokens_dot, _ = extract_product_query_tokens("harga minyak goreng 1.5 liter berapa?")
        assert "1.5liter" in all_tokens_dot

        all_tokens_comma, _ = extract_product_query_tokens("stok gula 0,5 kg ada?")
        assert "0.5kg" in all_tokens_comma

        variants = [
            ProductItem(id=1, sku="BRS-5KG", name="Beras Medium 5 kg", price=68000, stock=15, unit="sak", is_active=True),
            ProductItem(id=2, sku="BRS-25KG", name="Beras Medium 25 kg", price=330000, stock=8, unit="karung", is_active=True),
        ]
        m5 = match_product("harga beras 5 kg berapa?", variants)
        m25 = match_product("harga beras 25 kg berapa?", variants)
        assert m5.matched_product is not None and m5.matched_product.sku == "BRS-5KG"
        assert m25.matched_product is not None and m25.matched_product.sku == "BRS-25KG"


class TestStockStatusAndFormatting:
    """Verify deterministic stock thresholds and Indonesian currency/quantity formatting."""

    @pytest.mark.parametrize(
        ("stock", "threshold", "expected_status"),
        [
            (0.0, 5.0, "habis"),
            (-1.0, 5.0, "habis"),
            (0.5, 5.0, "menipis"),
            (3.0, 5.0, "menipis"),
            (5.0, 5.0, "menipis"),
            (5.1, 5.0, "tersedia"),
            (24.0, 5.0, "tersedia"),
        ],
    )
    def test_compute_stock_status_thresholds(
        self,
        stock: float,
        threshold: float,
        expected_status: str,
    ) -> None:
        assert compute_stock_status(stock, low_stock_threshold=threshold) == expected_status

    def test_match_product_assigns_expected_stock_statuses_from_catalog(
        self,
        sample_products: list[ProductItem],
    ) -> None:
        # stock == 0.000 -> habis
        habis = match_product("stok susu kental manis ada?", sample_products, low_stock_threshold=5.0)
        assert habis.matched_product is not None
        assert habis.matched_product.stock_status == "habis"

        # stock == 3.000 <= 5 -> menipis
        menipis = match_product("stok minyak goreng ada?", sample_products, low_stock_threshold=5.0)
        assert menipis.matched_product is not None
        assert menipis.matched_product.stock_status == "menipis"

        # stock == 24.000 > 5 -> tersedia
        tersedia = match_product("stok telur ada?", sample_products, low_stock_threshold=5.0)
        assert tersedia.matched_product is not None
        assert tersedia.matched_product.stock_status == "tersedia"

    def test_currency_and_stock_formatting(self) -> None:
        assert format_rupiah(17500.0) == "Rp17.500"
        assert format_rupiah(58000.00) == "Rp58.000"
        assert format_rupiah(12500.5) == "Rp12.500,50"
        assert format_stock_quantity(24.0) == "24"
        assert format_stock_quantity(3.5) == "3.5"
