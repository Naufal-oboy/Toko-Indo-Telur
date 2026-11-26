#!/usr/bin/env python3
"""
Evaluasi baseline intent chatbot Toko Indo Telur (Capstone Asah 2026, Tim A26-CS201).

Memvalidasi dataset (baris kosong, duplikat, label tak dikenal) lalu membandingkan
dua konfigurasi TF-IDF + Naive Bayes pada split dan metrik yang sama
(accuracy + macro-F1), sesuai TC-09 dan TC-12 di PRD.

Ini baseline pengujian dataset, bukan model final di ai-service.

Cara menjalankan (Python 3, tanpa library tambahan):
    python data-science/evaluasi_intent.py
    python data-science/evaluasi_intent.py path/ke/dataset.csv

Seluruh data bersifat dummy. Tidak ada chat atau nomor
pelanggan asli (PRD BR-09 / NFR-05).
"""
import csv
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CSV_PATH = Path(__file__).parent / "data" / "dataset_intent_dummy.csv"
CLASSES = ["sapaan", "format_pesanan", "cek_harga", "cek_stok", "lainnya"]
SEED = 42
TEST_PER_CLASS = 10  # 50 baris/kelas -> 40 train + 10 test per kelas


def tokenize(text: str):
    return re.findall(r"[a-z0-9]+", text.lower())


def ngrams(tokens, n_max):
    feats = []
    for n in range(1, n_max + 1):
        feats += [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]
    return feats


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    print(f"Baris dibaca: {len(rows)} dari {path.name}")
    # TC-12: validasi kosong / duplikat / intent tak dikenal
    empty = [r for r in rows if not r["text"].strip() or not r["intent"].strip()]
    dupes = [t for t, c in Counter(r["text"].strip().lower() for r in rows).items() if c > 1]
    unknown = sorted({r["intent"] for r in rows} - set(CLASSES))
    print(f"  kosong: {len(empty)} | teks duplikat: {len(dupes)} {dupes} | intent tak dikenal: {unknown or '-'}")
    print(f"  per kelas: {dict(Counter(r['intent'] for r in rows))}")
    assert not empty and not dupes and not unknown, "Dataset gagal validasi TC-12 — perbaiki CSV dulu."
    return [(r["text"], r["intent"]) for r in rows]


def split(data):
    rng = random.Random(SEED)
    train, test = [], []
    by_class = defaultdict(list)
    for item in data:
        by_class[item[1]].append(item)
    for cls in CLASSES:
        items = by_class[cls][:]
        rng.shuffle(items)
        test += items[:TEST_PER_CLASS]
        train += items[TEST_PER_CLASS:]
    return train, test


class TfidfNB:
    """Multinomial Naive Bayes di atas fitur TF-IDF (starter, bukan SOTA)."""

    def __init__(self, n_max=1, alpha=1.0):
        self.n_max, self.alpha = n_max, alpha

    def fit(self, data):
        docs = [[f for f in ngrams(tokenize(t), self.n_max)] for t, _ in data]
        df = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {f: math.log((n + 1) / (c + 1)) + 1.0 for f, c in df.items()}
        self.vocab = sorted(self.idf)
        self.prior = Counter(y for _, y in data)
        counts = {c: Counter() for c in CLASSES}
        for (t, y), d in zip(data, docs):
            tf = Counter(d)
            for f, k in tf.items():
                counts[y][f] += (k / len(d)) * self.idf.get(f, 1.0)
        self.tot = {c: sum(counts[c].values()) for c in CLASSES}
        self.counts = counts

    def predict(self, text):
        feats = ngrams(tokenize(text), self.n_max)
        tf = Counter(feats)
        best, best_score = None, -1e18
        for c in CLASSES:
            score = math.log(self.prior[c] / sum(self.prior.values()))
            denom = self.tot[c] + self.alpha * len(self.vocab)
            for f, k in tf.items():
                w = (k / max(len(feats), 1)) * self.idf.get(f, 1.0)
                score += w * math.log((self.counts[c][f] + self.alpha) / denom)
            if score > best_score:
                best, best_score = c, score
        return best


def metrics(gold, pred):
    acc = sum(g == p for g, p in zip(gold, pred)) / len(gold)
    f1s = []
    print(f"  {'kelas':<18} {'P':>5} {'R':>5} {'F1':>5}  (n test)")
    for c in CLASSES:
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
        print(f"  {c:<18} {prec:5.2f} {rec:5.2f} {f1:5.2f}  ({sum(g == c for g in gold)})")
    return acc, sum(f1s) / len(f1s)


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_PATH
    data = load(path)
    train, test = split(data)
    print(f"Train: {len(train)} | Test: {len(test)} (stratified, seed={SEED}, {TEST_PER_CLASS}/kelas)\n")
    configs = [
        ("A: TF-IDF 1-gram + NB alpha=1.0", TfidfNB(n_max=1, alpha=1.0)),
        ("B: TF-IDF 1-2 gram + NB alpha=0.1", TfidfNB(n_max=2, alpha=0.1)),
    ]
    results = {}
    for name, model in configs:
        model.fit(train)
        gold = [y for _, y in test]
        pred = [model.predict(t) for t, _ in test]
        print(name)
        acc, mf1 = metrics(gold, pred)
        results[name] = (acc, mf1)
        print(f"  -> accuracy={acc:.2f}  macro-F1={mf1:.2f}\n")
        for (t, g), p in zip(test, pred):
            if g != p:
                print(f"     SALAH: '{t}' gold={g} pred={p}")
    print("KESIMPULAN (data dummy 250 baris — JANGAN diklaim sebagai kinerja nyata):")
    best = max(results, key=lambda k: results[k][1])
    for name, (acc, mf1) in results.items():
        print(f"  {name}: accuracy={acc:.2f}, macro-F1={mf1:.2f}{'  <-- dipilih (macro-F1 tertinggi)' if name == best else ''}")
    print("  Catatan: seluruh data masih dummy, hasil ini hanya baseline pengujian dataset.")


if __name__ == "__main__":
    main()
