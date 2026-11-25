"""Typo-tolerant, active-only product matching and deterministic stock status."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from rapidfuzz import fuzz

from src.preprocessing import normalize_text
from src.schemas import MatchedProductInfo, ProductItem, QueryStatus, StockStatus

QUERY_STOPWORDS: frozenset[str] = frozenset(
    {
        # Intent & question words
        "stok",
        "stock",
        "stoknya",
        "stocknya",
        "ketersediaan",
        "ketersediaannya",
        "harga",
        "harganya",
        "berapa",
        "berapaan",
        "kisaran",
        "sekitar",
        "ada",
        "masih",
        "tersedia",
        "habis",
        "habisnya",
        "kosong",
        "kosongnya",
        "sisa",
        "sisanya",
        "aman",
        "banyak",
        "sedikit",
        "dikit",
        "kurang",
        "naik",
        "turun",
        "murah",
        "mahal",
        "paling",
        "lengkap",
        "promo",
        "diskon",
        "ongkir",
        "duit",
        "uang",
        "barang",
        "barangnya",
        "produk",
        "produknya",
        "sembako",
        "daftar",
        "pricelist",
        "list",
        "katalog",
        "gudang",
        "tokonya",
        "semua",
        "jenis",
        "merk",
        "merek",
        "varian",
        "ukuran",
        "minimal",
        "order",
        "orderan",
        "pesanan",
        "diantar",
        "antar",
        "satu",
        "apakah",
        "apa",
        "gimana",
        "bagaimana",
        "sekarang",
        "hari",
        "ini",
        "terbaru",
        "update",
        "saat",
        # Greetings & addressing
        "halo",
        "selamat",
        "pagi",
        "siang",
        "sore",
        "malam",
        "assalamualaikum",
        "permisi",
        "kak",
        "kakak",
        "bu",
        "ibu",
        "pak",
        "bapak",
        "bos",
        "boss",
        "mas",
        "mbak",
        "mba",
        "bang",
        "admin",
        "min",
        "toko",
        # Politeness & filler particles
        "tolong",
        "mohon",
        "bisa",
        "boleh",
        "dong",
        "deh",
        "sih",
        "ya",
        "iya",
        "yuk",
        "nih",
        "nya",
        "kah",
        "kan",
        "lah",
        "terima",
        "kasih",
        "saya",
        "aku",
        "kami",
        "kita",
        # Verbs / inquiry fillers
        "cek",
        "check",
        "tanya",
        "nanya",
        "info",
        "infonya",
        "lihat",
        "liat",
        "mau",
        "ingin",
        "pengen",
        "pesan",
        "belanja",
        "ambil",
        "butuh",
        "cari",
        "jual",
        "dijual",
        "punya",
        "tau",
        "tahu",
        "minta",
        "kirim",
        "bayar",
        "transfer",
        "dapat",
        # Negations / connectors / prepositions
        "tidak",
        "belum",
        "dan",
        "atau",
        "yang",
        "di",
        "ke",
        "dari",
        "untuk",
        "buat",
        "sama",
        "dengan",
        "itu",
        "sana",
        "sini",
        "lagi",
        "lg",
        "aja",
        "saja",
        "banget",
        "banyak",
        "kalau",
        "kalo",
        "jika",
        "bila",
        "sudah",
        "juga",
        "tapi",
        "karena",
        "dalam",
        # Units & commercial modifiers
        "per",
        "satuan",
        "ecer",
        "eceran",
        "grosir",
        "sekilo",
        "sekg",
        "serak",
        "sekarung",
        "sebungkus",
        "sebotol",
        "sedus",
        "seliter",
        "kg",
        "kilo",
        "kilogram",
        "gram",
        "gr",
        "liter",
        "ltr",
        "ml",
        "rak",
        "krat",
        "papan",
        "dus",
        "kardus",
        "karung",
        "sak",
        "botol",
        "btl",
        "pcs",
        "biji",
        "buah",
        "bungkus",
        "bks",
        "pack",
        "pak",
        "pouch",
        "kaleng",
        "butir",
        "kemasan",
        "renteng",
        "bal",
        "ball",
        "ready",
        "readynya",
        "disini",
        "situ",
        "tuh",
        "udah",
        "belom",
        "blm",
        "gaada",
        "baru",
        "lagi",
    }
)

_RAW_DECIMAL_RE = re.compile(r"(?<=\d)[.,](?=\d)")
_DECIMAL_TOKEN_PLACEHOLDER = "xdecx"
_QUANTITY_OR_SIZE_RE = re.compile(
    r"^\d+(?:\.\d+)?(?:kg|kilo|g|gr|gram|l|ltr|liter|ml|pcs|rak|dus|sak|btl|bks)?$"
)
_COMPACT_SIZE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s+(kg|kilo|g|gr|gram|l|ltr|liter|ml|pcs|rak|dus|sak|btl|bks)\b"
)
_SIZE_UNIT_ALIASES: dict[str, str] = {
    "kilo": "kg",
    "gr": "gram",
    "g": "gram",
    "l": "liter",
    "ltr": "liter",
    "btl": "botol",
    "bks": "bungkus",
}
_SPLIT_SIZE_RE = re.compile(
    r"^(\d+(?:\.\d+)?)(kg|kilo|g|gr|gram|l|ltr|liter|ml|pcs|rak|dus|sak|btl|bks)$"
)


@dataclass(frozen=True)
class ProductMatchResult:
    """Structured result of matching a customer message against active products."""

    query_status: QueryStatus
    extracted_query: str
    matched_product: MatchedProductInfo | None
    active_product_count: int


def compute_stock_status(stock: float, low_stock_threshold: float = 5.0) -> StockStatus:
    """Deterministically map numeric stock to habis / menipis / tersedia."""
    if stock <= 0:
        return "habis"
    if stock <= low_stock_threshold:
        return "menipis"
    return "tersedia"


def format_rupiah(price: float) -> str:
    """Format numeric price into Indonesian Rupiah string (e.g. Rp17.500)."""
    rounded = round(float(price), 2)
    if rounded.is_integer():
        integer_str = f"{int(rounded):,}".replace(",", ".")
        return f"Rp{integer_str}"
    integer_part = int(rounded)
    decimal_part = int(round((rounded - integer_part) * 100))
    integer_str = f"{integer_part:,}".replace(",", ".")
    return f"Rp{integer_str},{decimal_part:02d}"


def format_stock_quantity(stock: float) -> str:
    """Format stock quantity without noisy trailing decimal zeros."""
    val = float(stock)
    if val.is_integer():
        return str(int(val))
    return f"{val:g}"


def _normalize_preserving_decimals(text: str) -> str:
    """Normalize text while keeping decimal numbers (e.g., 1.5 liter, 0,5 kg) intact."""
    if not text:
        return ""
    protected = _RAW_DECIMAL_RE.sub(_DECIMAL_TOKEN_PLACEHOLDER, str(text))
    normalized = normalize_text(protected)
    return normalized.replace(_DECIMAL_TOKEN_PLACEHOLDER, ".")


def _canonicalize_size_token(token: str) -> str:
    match = _SPLIT_SIZE_RE.match(token)
    if not match:
        return token
    amount, unit = match.group(1), match.group(2)
    canonical_unit = _SIZE_UNIT_ALIASES.get(unit, unit)
    return f"{amount}{canonical_unit}"


def _compact_sizes(text: str) -> str:
    compacted = _COMPACT_SIZE_RE.sub(r"\1\2", text)
    return " ".join(_canonicalize_size_token(tok) for tok in compacted.split())


def extract_product_query_tokens(message: str) -> tuple[list[str], list[str]]:
    """Extract candidate product tokens after removing Indonesian inquiry stopwords.

    Returns:
        Tuple of ``(all_non_stopword_tokens, meaningful_word_tokens)``.
        If ``meaningful_word_tokens`` is empty, no product name was mentioned.
    """
    normalized = _compact_sizes(_normalize_preserving_decimals(message))
    if not normalized:
        return [], []

    all_tokens: list[str] = []
    word_tokens: list[str] = []

    for token in normalized.split():
        if token in QUERY_STOPWORDS:
            continue
        # Strip Indonesian possessive '-nya' (e.g. 'telurnya' -> 'telur', 'stoknya' -> stopword)
        if len(token) > 4 and token.endswith("nya"):
            stem = token[:-3]
            if stem in QUERY_STOPWORDS:
                continue
            token = stem
        all_tokens.append(token)
        if not _QUANTITY_OR_SIZE_RE.match(token) and len(token) >= 2:
            word_tokens.append(token)

    return all_tokens, word_tokens


def _coerce_products(products: Sequence[ProductItem | dict[str, Any]]) -> list[ProductItem]:
    parsed: list[ProductItem] = []
    for item in products:
        if isinstance(item, ProductItem):
            parsed.append(item)
        elif isinstance(item, dict):
            parsed.append(ProductItem.model_validate(item))
    return parsed


def _score_product(
    query_tokens: list[str],
    query_word_tokens: list[str],
    product: ProductItem,
) -> tuple[float, float, float]:
    """Compute (primary_score, min_token_score, tiebreaker_score) for a product."""
    query_full = " ".join(query_tokens)
    query_words_str = " ".join(query_word_tokens)

    # 1. Exact SKU match
    if product.sku:
        sku_norm = normalize_text(product.sku)
        sku_compact = re.sub(r"\s+", "", sku_norm)
        query_compact = re.sub(r"\s+", "", query_full)
        if sku_compact and (sku_compact == query_compact or sku_compact in query_tokens):
            return 100.0, 100.0, 100.0

    prod_norm = _compact_sizes(_normalize_preserving_decimals(product.name))
    prod_tokens = prod_norm.split()
    if not prod_tokens:
        return 0.0, 0.0, 0.0

    prod_word_tokens = [
        tok
        for tok in prod_tokens
        if tok not in QUERY_STOPWORDS and not _QUANTITY_OR_SIZE_RE.match(tok)
    ]

    # 2. Token-to-token RapidFuzz alignment (prevents substring false positives)
    best_per_token: list[float] = []
    for q_tok in query_word_tokens:
        best_sim = max(fuzz.ratio(q_tok, p_tok) for p_tok in prod_tokens)
        best_per_token.append(float(best_sim))

    avg_token_score = sum(best_per_token) / len(best_per_token)
    min_token_score = min(best_per_token)

    # 3. Handle joined compound words (e.g. "gulapasir" vs "gula pasir")
    if len(query_word_tokens) == 1 and len(prod_word_tokens) >= 2:
        q_single = query_word_tokens[0]
        bigram_scores = [
            float(fuzz.ratio(q_single, prod_word_tokens[i] + prod_word_tokens[i + 1]))
            for i in range(len(prod_word_tokens) - 1)
        ]
        best_compound = max(bigram_scores, default=0.0)
        if best_compound > avg_token_score:
            avg_token_score = best_compound
            min_token_score = best_compound

    # 4. Tie-breaker: size token agreement + WRatio similarity
    size_tokens = [tok for tok in query_tokens if _QUANTITY_OR_SIZE_RE.match(tok)]
    prod_size_tokens = [tok for tok in prod_tokens if _QUANTITY_OR_SIZE_RE.match(tok)]
    size_bonus = 0.0
    if size_tokens:
        matched_sizes = sum(1 for st in size_tokens if st in prod_size_tokens)
        if matched_sizes > 0:
            size_bonus = (matched_sizes / len(size_tokens)) * 15.0
        elif prod_size_tokens:
            # Penalize tiebreaker when user requested a specific size that disagrees with product size
            size_bonus = -5.0

    wratio = float(fuzz.WRatio(query_full, prod_norm))
    word_set = float(fuzz.token_set_ratio(query_words_str, prod_norm))
    tiebreaker = size_bonus + (0.6 * wratio) + (0.4 * word_set)

    return avg_token_score, min_token_score, tiebreaker


def match_product(
    message: str,
    products: Sequence[ProductItem | dict[str, Any]],
    low_stock_threshold: float = 5.0,
    min_match_score: float = 78.0,
) -> ProductMatchResult:
    """Match a customer message against active products only (is_active == True)."""
    parsed_products = _coerce_products(products)
    active_products = [product for product in parsed_products if product.is_active is True]

    query_tokens, query_word_tokens = extract_product_query_tokens(message)
    extracted_query = " ".join(query_tokens)

    if not query_word_tokens:
        return ProductMatchResult(
            query_status="missing_product_name",
            extracted_query="",
            matched_product=None,
            active_product_count=len(active_products),
        )

    if not active_products:
        return ProductMatchResult(
            query_status="not_found",
            extracted_query=extracted_query,
            matched_product=None,
            active_product_count=0,
        )

    best_product: ProductItem | None = None
    best_primary = 0.0
    best_min_tok = 0.0
    best_tiebreaker = -1.0

    for product in active_products:
        primary, min_tok, tiebreaker = _score_product(
            query_tokens=query_tokens,
            query_word_tokens=query_word_tokens,
            product=product,
        )
        is_better = (primary > best_primary) or (
            abs(primary - best_primary) < 1e-6 and tiebreaker > best_tiebreaker
        )
        if is_better:
            best_product = product
            best_primary = primary
            best_min_tok = min_tok
            best_tiebreaker = tiebreaker

    min_token_floor = 72.0 if len(query_word_tokens) > 1 else min_match_score
    if (
        best_product is None
        or best_primary < min_match_score
        or best_min_tok < min_token_floor
    ):
        return ProductMatchResult(
            query_status="not_found",
            extracted_query=extracted_query,
            matched_product=None,
            active_product_count=len(active_products),
        )

    matched = MatchedProductInfo(
        id=best_product.id,
        sku=best_product.sku,
        name=best_product.name,
        price=best_product.price,
        formatted_price=format_rupiah(best_product.price),
        stock=best_product.stock,
        unit=best_product.unit,
        stock_status=compute_stock_status(best_product.stock, low_stock_threshold),
        match_score=round(best_primary, 2),
        is_active=True,
    )

    return ProductMatchResult(
        query_status="matched",
        extracted_query=extracted_query,
        matched_product=matched,
        active_product_count=len(active_products),
    )
