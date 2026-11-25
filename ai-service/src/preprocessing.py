"""Text normalization and Indonesian grocery chat typo handling for Toko Indo Telur."""

from __future__ import annotations

import re

TYPO_MAP: dict[str, str] = {
    # Produk sembako & varian ejaan/typo
    "telor": "telur",
    "teloor": "telur",
    "tlur": "telur",
    "tlr": "telur",
    "gulaa": "gula",
    "gulla": "gula",
    "gla": "gula",
    "migor": "minyak goreng",
    "mnyak": "minyak",
    "minyk": "minyak",
    "trigu": "terigu",
    "teriguu": "terigu",
    "tpung": "tepung",
    "tpg": "tepung",
    "brs": "beras",
    "berass": "beras",
    "kcp": "kecap",
    "kecapp": "kecap",
    "grm": "garam",
    "garamm": "garam",
    "mi": "mie",
    "miee": "mie",
    # Kata tanya harga & stok
    "brp": "berapa",
    "brpa": "berapa",
    "brapa": "berapa",
    "berapaa": "berapa",
    "berap": "berapa",
    "brpan": "berapa",
    "berapaan": "berapa",
    "hrg": "harga",
    "hrga": "harga",
    "hargaa": "harga",
    "harg": "harga",
    "stk": "stok",
    "stock": "stok",
    "stokk": "stok",
    "stoc": "stok",
    "ready": "ada",
    "redi": "ada",
    "redy": "ada",
    "readyy": "ada",
    "adaa": "ada",
    "msh": "masih",
    "msih": "masih",
    "tersediaa": "tersedia",
    "kosongg": "kosong",
    "habiss": "habis",
    "abis": "habis",
    # Negasi & partikel chat
    "ga": "tidak",
    "gak": "tidak",
    "gk": "tidak",
    "ngga": "tidak",
    "nggak": "tidak",
    "enggak": "tidak",
    "tdk": "tidak",
    "tak": "tidak",
    "ndak": "tidak",
    "nda": "tidak",
    # Pemesanan
    "psn": "pesan",
    "pesen": "pesan",
    "order": "pesan",
    "ordr": "pesan",
    "beli": "pesan",
    "blanja": "belanja",
    "mw": "mau",
    "mauu": "mau",
    "gmn": "gimana",
    "gmna": "gimana",
    "gimna": "gimana",
    "gmana": "gimana",
    "bgmn": "gimana",
    "bgmana": "gimana",
    # Sapaan
    "halo": "halo",
    "hallo": "halo",
    "haloo": "halo",
    "hai": "halo",
    "haii": "halo",
    "hi": "halo",
    "helo": "halo",
    "hello": "halo",
    "p": "halo",
    "pp": "halo",
    "ass": "assalamualaikum",
    "asslm": "assalamualaikum",
    "aslm": "assalamualaikum",
    "assalamuallaikum": "assalamualaikum",
    "assalammualaikum": "assalamualaikum",
    "pgi": "pagi",
    "pagii": "pagi",
    "sng": "siang",
    "siangg": "siang",
    "soree": "sore",
    "mlm": "malam",
    "malamm": "malam",
    "misi": "permisi",
    "misii": "permisi",
    "permisii": "permisi",
    # Singkatan chat umum bahasa Indonesia
    "sy": "saya",
    "sya": "saya",
    "bs": "bisa",
    "bsa": "bisa",
    "bisaa": "bisa",
    "yg": "yang",
    "utk": "untuk",
    "tuk": "untuk",
    "bwt": "untuk",
    "dgn": "dengan",
    "dg": "dengan",
    "klo": "kalau",
    "klau": "kalau",
    "kl": "kalau",
    "jg": "juga",
    "jga": "juga",
    "udh": "sudah",
    "sdh": "sudah",
    "blm": "belum",
    "skrg": "sekarang",
    "skg": "sekarang",
    "hr": "hari",
    "hri": "hari",
    "dlm": "dalam",
    "krn": "karena",
    "tp": "tapi",
    "tpi": "tapi",
    "bgt": "banget",
    "bnyk": "banyak",
    "byk": "banyak",
    "tlg": "tolong",
    "tlng": "tolong",
    "dng": "dong",
    "donk": "dong",
    "dongg": "dong",
    "krm": "kirim",
    "byr": "bayar",
    "tf": "transfer",
    "rek": "rekening",
    "trims": "terima kasih",
    "mksh": "terima kasih",
    "makasih": "terima kasih",
    "thx": "terima kasih",
    "tks": "terima kasih",
    "kk": "kak",
    "yaa": "ya",
    "iyaa": "iya",
    "dpt": "dapat",
}

_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
_REPEAT_3PLUS_RE = re.compile(r"(.)\1{2,}")
_TRAILING_DOUBLE_VOWEL_RE = re.compile(r"([aiueo])\1+$")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize Indonesian grocery customer chat text for classification and matching.

    Steps:
    1. Casefold to lowercase.
    2. Strip noisy punctuation/symbols while preserving alphanumeric characters and spaces.
    3. Collapse 3+ consecutive repeated characters (e.g., ``gulaaaa`` -> ``gula``).
    4. Map tokens through ``TYPO_MAP``; if not directly matched, also collapse
       trailing doubled vowels (e.g., ``gulaa`` -> ``gula``, ``berapaa`` -> ``berapa``)
       and re-check ``TYPO_MAP``.
    5. Collapse repeated whitespace and strip leading/trailing spaces.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    cleaned = text.lower()
    cleaned = _NON_ALNUM_RE.sub(" ", cleaned)
    cleaned = _REPEAT_3PLUS_RE.sub(r"\1", cleaned)

    tokens = cleaned.split()
    normalized_tokens: list[str] = []
    for token in tokens:
        mapped = TYPO_MAP.get(token)
        if mapped is not None:
            normalized_tokens.append(mapped)
            continue

        trimmed = _TRAILING_DOUBLE_VOWEL_RE.sub(r"\1", token)
        mapped_trimmed = TYPO_MAP.get(trimmed)
        if mapped_trimmed is not None:
            normalized_tokens.append(mapped_trimmed)
        else:
            normalized_tokens.append(trimmed)

    return _WHITESPACE_RE.sub(" ", " ".join(normalized_tokens)).strip()
