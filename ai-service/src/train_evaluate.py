"""Train, compare, evaluate, and export intent classification models for Toko Indo Telur.

Usage:
    python src/train_evaluate.py
    python src/train_evaluate.py --dataset data/intent_dataset_dummy.csv \
        --output-model artifacts/intent_model.joblib \
        --output-report artifacts/evaluation_report.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

AI_SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from src.preprocessing import normalize_text  # noqa: E402
from src.schemas import VALID_INTENTS  # noqa: E402

DATASET_DISCLAIMER = (
    "Dataset dummy sintetis tanpa identitas pelanggan, nomor telepon, atau isi chat asli "
    "(sesuai BR-09). Digunakan untuk pengembangan & evaluasi awal sebelum handoff dataset "
    "final DS-04; metrik pada data dummy tidak diklaim mewakili performa produksi nyata."
)
CUSTOM_DATASET_DISCLAIMER = (
    "Dataset kustom/handoff tanpa identitas pelanggan (sesuai BR-09). "
    "Pembagian train/test telah dideduplikasi sebelum split untuk mencegah kebocoran data; "
    "pastikan sumber, izin, dan keterbatasan dataset terdokumentasi di README."
)

DEFAULT_DATASET_PATH = AI_SERVICE_ROOT / "data" / "intent_dataset_dummy.csv"
DEFAULT_OUTPUT_MODEL_PATH = AI_SERVICE_ROOT / "artifacts" / "intent_model.joblib"
DEFAULT_OUTPUT_REPORT_PATH = AI_SERVICE_ROOT / "artifacts" / "evaluation_report.json"


def load_and_clean_dataset(dataset_path: Path) -> tuple[list[str], list[str], int, int]:
    """Load CSV, validate intents, normalize text, detect label conflicts, and deduplicate."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    raw_rows = 0
    seen_text_to_label: dict[str, str] = {}
    invalid_intents: set[str] = set()
    conflicting_texts: list[tuple[str, str, str]] = []
    texts: list[str] = []
    labels: list[str] = []
    allowed_intents = set(VALID_INTENTS)

    with dataset_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "text" not in reader.fieldnames or "intent" not in reader.fieldnames:
            raise ValueError("Dataset CSV must contain 'text' and 'intent' columns.")

        for row in reader:
            raw_rows += 1
            norm_text = normalize_text(row.get("text", ""))
            intent = (row.get("intent") or "").strip()
            if not norm_text or not intent:
                continue
            if intent not in allowed_intents:
                invalid_intents.add(intent)
                continue
            if norm_text in seen_text_to_label:
                prev_label = seen_text_to_label[norm_text]
                if prev_label != intent:
                    conflicting_texts.append((norm_text, prev_label, intent))
                continue
            seen_text_to_label[norm_text] = intent
            texts.append(norm_text)
            labels.append(intent)

    if invalid_intents:
        raise ValueError(
            f"Dataset contains invalid intent label(s): {sorted(invalid_intents)}. "
            f"Allowed intents: {list(VALID_INTENTS)}."
        )
    if conflicting_texts:
        sample_conflict = conflicting_texts[0]
        raise ValueError(
            f"Dataset contains {len(conflicting_texts)} duplicate normalized text(s) with "
            f"conflicting intent labels (e.g. {sample_conflict[0]!r}: "
            f"{sample_conflict[1]!r} vs {sample_conflict[2]!r})."
        )

    if len(texts) < 10:
        raise ValueError(f"Too few valid unique rows ({len(texts)}) in dataset: {dataset_path}")

    return texts, labels, raw_rows, len(texts)


def build_candidate_pipelines(random_state: int = 42) -> dict[str, tuple[str, Pipeline]]:
    """Return the 3 candidate scikit-learn pipelines accepting already-normalized strings."""
    return {
        "tfidf_logreg": (
            "FeatureUnion(TF-IDF word 1-2 + char_wb 3-5) + LogisticRegression(max_iter=1000)",
            Pipeline(
                [
                    (
                        "features",
                        FeatureUnion(
                            [
                                ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                                (
                                    "char",
                                    TfidfVectorizer(
                                        analyzer="char_wb",
                                        ngram_range=(3, 5),
                                        sublinear_tf=True,
                                    ),
                                ),
                            ]
                        ),
                    ),
                    ("clf", LogisticRegression(max_iter=1000, random_state=random_state)),
                ]
            ),
        ),
        "tfidf_linear_svc": (
            "FeatureUnion(TF-IDF word 1-2 + char_wb 3-5) + CalibratedClassifierCV(LinearSVC, cv=3)",
            Pipeline(
                [
                    (
                        "features",
                        FeatureUnion(
                            [
                                ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                                (
                                    "char",
                                    TfidfVectorizer(
                                        analyzer="char_wb",
                                        ngram_range=(3, 5),
                                        sublinear_tf=True,
                                    ),
                                ),
                            ]
                        ),
                    ),
                    (
                        "clf",
                        CalibratedClassifierCV(
                            LinearSVC(random_state=random_state),
                            cv=3,
                        ),
                    ),
                ]
            ),
        ),
        "tfidf_multinomial_nb": (
            "TfidfVectorizer(word 1-2) + MultinomialNB()",
            Pipeline(
                [
                    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                    ("clf", MultinomialNB()),
                ]
            ),
        ),
    }


def measure_avg_inference_ms(pipeline: Pipeline, samples: list[str], repeats: int = 3) -> float:
    """Measure average single-sample predict_proba latency in milliseconds."""
    if not samples:
        return 0.0
    # Warmup call
    pipeline.predict_proba([samples[0]])

    start = time.perf_counter()
    total_calls = 0
    for _ in range(repeats):
        for text in samples:
            pipeline.predict_proba([text])
            total_calls += 1
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return round(elapsed_ms / max(total_calls, 1), 4)


def run_training_pipeline(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    output_model_path: Path = DEFAULT_OUTPUT_MODEL_PATH,
    output_report_path: Path = DEFAULT_OUTPUT_REPORT_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    """Execute full deduplication, stratified split, 3-model comparison, and artifact export."""
    texts, labels, total_rows_raw, total_rows_deduped = load_and_clean_dataset(dataset_path)
    class_distribution = dict(sorted(Counter(labels).items()))
    classes = sorted(class_distribution.keys())

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=test_size,
        random_state=random_state,
        stratify=labels,
    )

    # Strict leakage guard: no normalized text may appear in both splits
    overlap = set(x_train).intersection(set(x_test))
    if overlap:
        raise RuntimeError(f"Data leakage detected between train and test splits: {len(overlap)} overlapping rows.")

    candidates = build_candidate_pipelines(random_state=random_state)
    trained_pipelines: dict[str, Pipeline] = {}
    models_report: dict[str, dict[str, Any]] = {}

    min_train_class_count = min(Counter(y_train).values())
    cv_splits = min(5, min_train_class_count)

    for model_name, (description, pipeline) in candidates.items():
        cv_summary: dict[str, Any] | None = None
        if cv_splits >= 2:
            cv_candidates = build_candidate_pipelines(random_state=random_state)
            _, cv_pipeline = cv_candidates[model_name]
            skf = StratifiedKFold(n_splits=cv_splits, shuffle=True, random_state=random_state)
            cv_res = cross_validate(
                cv_pipeline,
                x_train,
                y_train,
                cv=skf,
                scoring={"accuracy": "accuracy", "macro_f1": "f1_macro"},
            )
            cv_summary = {
                "n_splits": cv_splits,
                "accuracy_mean": round(float(cv_res["test_accuracy"].mean()), 4),
                "accuracy_std": round(float(cv_res["test_accuracy"].std()), 4),
                "macro_f1_mean": round(float(cv_res["test_macro_f1"].mean()), 4),
                "macro_f1_std": round(float(cv_res["test_macro_f1"].std()), 4),
            }

        pipeline.fit(x_train, y_train)
        y_pred = pipeline.predict(x_test)

        accuracy = round(float(accuracy_score(y_test, y_pred)), 4)
        macro_f1 = round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4)
        per_class_report = classification_report(
            y_test,
            y_pred,
            labels=classes,
            output_dict=True,
            zero_division=0,
        )
        cm = confusion_matrix(y_test, y_pred, labels=classes).tolist()
        avg_inf_ms = measure_avg_inference_ms(pipeline, x_test)

        trained_pipelines[model_name] = pipeline
        models_report[model_name] = {
            "description": description,
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "avg_inference_ms": avg_inf_ms,
            "confusion_matrix": cm,
            "cv_train_summary": cv_summary,
            "per_class_report": per_class_report,
        }

    # Select best model: highest macro_f1, tie-breaker highest accuracy, then lowest avg_inference_ms
    selected_model = max(
        models_report.keys(),
        key=lambda name: (
            models_report[name]["macro_f1"],
            models_report[name]["accuracy"],
            -models_report[name]["avg_inference_ms"],
        ),
    )

    best_metrics = models_report[selected_model]
    selection_reason = (
        f"Dipilih '{selected_model}' berdasarkan Macro-F1 tertinggi ({best_metrics['macro_f1']:.4f}), "
        f"dengan Accuracy {best_metrics['accuracy']:.4f} dan rata-rata latensi inferensi "
        f"{best_metrics['avg_inference_ms']:.4f} ms/pesan pada test set identik ({len(x_test)} sampel)."
    )

    best_pipeline = trained_pipelines[selected_model]
    trained_at = datetime.now(timezone.utc).isoformat()

    model_artifact: dict[str, Any] = {
        "model_name": selected_model,
        "pipeline": best_pipeline,
        "classes": [str(c) for c in best_pipeline.classes_],
        "trained_at": trained_at,
        "metrics": {
            "accuracy": best_metrics["accuracy"],
            "macro_f1": best_metrics["macro_f1"],
            "avg_inference_ms": best_metrics["avg_inference_ms"],
        },
    }

    output_model_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_artifact, output_model_path)

    train_pct = round((1.0 - test_size) * 100)
    test_pct = round(test_size * 100)
    try:
        display_dataset_path = dataset_path.resolve().relative_to(AI_SERVICE_ROOT).as_posix()
    except ValueError:
        display_dataset_path = str(dataset_path)

    is_default_dummy = dataset_path.resolve() == DEFAULT_DATASET_PATH.resolve()
    dataset_disclaimer = DATASET_DISCLAIMER if is_default_dummy else CUSTOM_DATASET_DISCLAIMER

    report: dict[str, Any] = {
        "dataset_path": display_dataset_path,
        "dataset_disclaimer": dataset_disclaimer,
        "trained_at": trained_at,
        "total_rows_raw": total_rows_raw,
        "total_rows_deduped": total_rows_deduped,
        "train_size": len(x_train),
        "test_size": len(x_test),
        "split_ratio": f"{train_pct}/{test_pct}",
        "random_state": random_state,
        "classes": classes,
        "class_distribution": class_distribution,
        "models": models_report,
        "selected_model": selected_model,
        "selection_reason": selection_reason,
    }

    with output_report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and evaluate 3 intent classification models for Toko Indo Telur."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to CSV dataset with columns 'text,intent'.",
    )
    parser.add_argument(
        "--output-model",
        type=Path,
        default=DEFAULT_OUTPUT_MODEL_PATH,
        help="Path to save the best model joblib artifact.",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=DEFAULT_OUTPUT_REPORT_PATH,
        help="Path to save the JSON evaluation report.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Test split fraction (default: 0.2 for 80/20 split).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducible train/test split and models (default: 42).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    report = run_training_pipeline(
        dataset_path=args.dataset,
        output_model_path=args.output_model,
        output_report_path=args.output_report,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print(f"Dataset: {report['dataset_path']} (raw={report['total_rows_raw']}, deduped={report['total_rows_deduped']})")
    print(f"Split: {report['split_ratio']} (train={report['train_size']}, test={report['test_size']})")
    for model_name, metrics in report["models"].items():
        print(
            f"  - {model_name:22s} | Accuracy={metrics['accuracy']:.4f} | "
            f"Macro-F1={metrics['macro_f1']:.4f} | Latency={metrics['avg_inference_ms']:.4f} ms"
        )
    print(f"Selected: {report['selected_model']}")
    print(f"Model saved to: {args.output_model}")
    print(f"Report saved to: {args.output_report}")


if __name__ == "__main__":
    main()
