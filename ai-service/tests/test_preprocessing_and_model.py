"""Tests for text preprocessing, leakage-free splitting, and model evaluation artifacts (TC-09, AI-01, AI-03)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import joblib
import pytest
from sklearn.model_selection import train_test_split

from src.preprocessing import TYPO_MAP, normalize_text
from src.train_evaluate import load_and_clean_dataset, run_training_pipeline

EXPECTED_CLASSES = {
    "sapaan",
    "format_pesanan",
    "cek_stok",
    "cek_harga",
    "lainnya",
}


class TestPreprocessing:
    """Verify Indonesian grocery text normalization and typo handling."""

    @pytest.mark.parametrize(
        ("raw_text", "expected"),
        [
            ("Stok telor ada?", "stok telur ada"),
            ("Harga gulaa brp???", "harga gula berapa"),
            ("HALOOOOOO!!!", "halo"),
            ("gulaaaa berapaa skrg?", "gula berapa sekarang"),
            ("migor 2 liter ready ga?", "minyak goreng 2 liter ada tidak"),
            ("mw psn trigu 5kg dongg!!", "mau pesan terigu 5kg dong"),
            ("   hrg   brs   brpa   yaa???  ", "harga beras berapa ya"),
            ("!!!???...", ""),
        ],
    )
    def test_normalize_text_handles_typos_repeats_and_punctuation(
        self,
        raw_text: str,
        expected: str,
    ) -> None:
        assert normalize_text(raw_text) == expected

    def test_normalize_text_handles_none_safely(self) -> None:
        assert normalize_text(None) == ""  # type: ignore[arg-type]

    def test_typo_map_contains_core_grocery_mappings(self) -> None:
        assert TYPO_MAP["telor"] == "telur"
        assert TYPO_MAP["gulaa"] == "gula"
        assert TYPO_MAP["brp"] == "berapa"
        assert TYPO_MAP["migor"] == "minyak goreng"
        assert TYPO_MAP["ready"] == "ada"
        # 'min' must not be globally rewritten to 'admin' (preserves 'min order')
        assert "min" not in TYPO_MAP
        assert normalize_text("min order berapa?") == "min pesan berapa"


class TestModelArtifactsAndEvaluation:
    """Verify trained model artifacts, >=2 model comparison, and leakage-free split."""

    def test_evaluation_report_and_model_artifacts_exist_and_are_consistent(
        self,
        ai_service_root: Path,
    ) -> None:
        report_path = ai_service_root / "artifacts" / "evaluation_report.json"
        model_path = ai_service_root / "artifacts" / "intent_model.joblib"

        assert report_path.exists(), f"Missing evaluation report: {report_path}"
        assert model_path.exists(), f"Missing model artifact: {model_path}"

        report = json.loads(report_path.read_text(encoding="utf-8"))

        # Split metadata & 80/20 deduped invariant
        assert report["split_ratio"] == "80/20"
        assert report["total_rows_deduped"] <= report["total_rows_raw"]
        assert report["train_size"] + report["test_size"] == report["total_rows_deduped"]
        assert report["test_size"] == round(report["total_rows_deduped"] * 0.2)
        assert set(report["classes"]) == EXPECTED_CLASSES

        # At least 2 models compared on identical test set
        models = report["models"]
        assert len(models) >= 2
        for model_name, metrics in models.items():
            assert 0.0 <= metrics["accuracy"] <= 1.0, f"Invalid accuracy for {model_name}"
            assert 0.0 <= metrics["macro_f1"] <= 1.0, f"Invalid macro_f1 for {model_name}"
            assert metrics["avg_inference_ms"] >= 0.0
            per_class = metrics["per_class_report"]
            assert int(per_class["macro avg"]["support"]) == report["test_size"]

        # Selected model must match highest Macro-F1 (tie-breakers: Accuracy, lowest latency)
        expected_best = max(
            models.keys(),
            key=lambda name: (
                models[name]["macro_f1"],
                models[name]["accuracy"],
                -models[name]["avg_inference_ms"],
            ),
        )
        assert report["selected_model"] == expected_best

        # Joblib artifact integrity
        artifact = joblib.load(model_path)
        assert isinstance(artifact, dict)
        assert artifact["model_name"] == report["selected_model"]
        assert set(artifact["classes"]) == EXPECTED_CLASSES
        assert hasattr(artifact["pipeline"], "predict_proba")

        probs = artifact["pipeline"].predict_proba([normalize_text("stok telor ada?")])[0]
        assert len(probs) == len(artifact["classes"])
        assert pytest.approx(sum(probs), rel=1e-4) == 1.0

    def test_dataset_dedup_prevents_train_test_data_leakage(
        self,
        ai_service_root: Path,
        tmp_path: Path,
    ) -> None:
        # 1. Verify on the repository dummy dataset
        dataset_path = ai_service_root / "data" / "intent_dataset_dummy.csv"
        texts, labels, raw_count, deduped_count = load_and_clean_dataset(dataset_path)
        assert raw_count >= deduped_count
        assert len(texts) == len(set(texts)) == deduped_count

        x_train, x_test, _, _ = train_test_split(
            texts,
            labels,
            test_size=0.2,
            random_state=42,
            stratify=labels,
        )
        assert set(x_train).isdisjoint(set(x_test))

        # 2. Verify on synthetic CSV containing typo/case duplicates that normalize identically
        dup_csv = tmp_path / "dup_dataset.csv"
        rows = [
            # Intentional duplicates after normalization
            ("stok telor ada?", "cek_stok"),
            ("STOK TELUR ADA!!!", "cek_stok"),
            ("stok telur adaaa??", "cek_stok"),
            ("stok gula masih ada?", "cek_stok"),
            ("stok beras 5kg ada?", "cek_stok"),
            ("stok minyak goreng ada?", "cek_stok"),
            ("stok tepung terigu ada?", "cek_stok"),
            ("stok kecap manis ready?", "cek_stok"),
            ("stok garam dapur ada?", "cek_stok"),
            ("stok mie instan masih ada?", "cek_stok"),
            ("stok susu kaleng ada?", "cek_stok"),
            ("stok kopi sachet ada?", "cek_stok"),
            ("harga gulaa brp?", "cek_harga"),
            ("HARGA GULA BERAPA???", "cek_harga"),
            ("harga telur satu rak berapa?", "cek_harga"),
            ("harga beras 5kg berapa?", "cek_harga"),
            ("harga minyak goreng berapa?", "cek_harga"),
            ("harga tepung terigu berapa?", "cek_harga"),
            ("harga kecap manis berapa?", "cek_harga"),
            ("harga garam halus berapa?", "cek_harga"),
            ("harga mie instan dus berapa?", "cek_harga"),
            ("harga susu kaleng berapa?", "cek_harga"),
            ("harga kopi renteng berapa?", "cek_harga"),
        ]
        with dup_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["text", "intent"])
            writer.writerows(rows)

        syn_texts, _, syn_raw, syn_deduped = load_and_clean_dataset(dup_csv)
        assert syn_raw == len(rows)
        # 3 duplicates collapsed (2 for telur, 1 for gula)
        assert syn_deduped == len(rows) - 3
        assert len(syn_texts) == len(set(syn_texts))

        # 3. End-to-end training run writing to temporary output paths only
        tmp_model = tmp_path / "intent_model.joblib"
        tmp_report = tmp_path / "evaluation_report.json"
        report = run_training_pipeline(
            dataset_path=dataset_path,
            output_model_path=tmp_model,
            output_report_path=tmp_report,
            test_size=0.2,
            random_state=42,
        )
        assert tmp_model.exists()
        assert tmp_report.exists()
        assert report["train_size"] + report["test_size"] == report["total_rows_deduped"]
        assert len(report["models"]) == 3
        for metrics in report["models"].values():
            assert isinstance(metrics["confusion_matrix"], list)
            assert len(metrics["confusion_matrix"]) == len(EXPECTED_CLASSES)
            assert metrics["cv_train_summary"] is not None
            assert metrics["cv_train_summary"]["n_splits"] == 5

    def test_dataset_validation_rejects_invalid_and_conflicting_labels(
        self,
        tmp_path: Path,
    ) -> None:
        # 1. Invalid intent label must raise ValueError before training
        invalid_csv = tmp_path / "invalid_intent.csv"
        with invalid_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["text", "intent"])
            writer.writerow(["halo kak", "sapaan"])
            writer.writerow(["stok telur ada?", "cek_stokk_typo"])

        with pytest.raises(ValueError, match="invalid intent label"):
            load_and_clean_dataset(invalid_csv)

        # 2. Duplicate normalized text with conflicting labels must raise ValueError
        conflict_csv = tmp_path / "conflict_intent.csv"
        with conflict_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["text", "intent"])
            writer.writerow(["stok telor ada?", "cek_stok"])
            writer.writerow(["STOK TELUR ADA!!!", "cek_harga"])

        with pytest.raises(ValueError, match="conflicting intent labels"):
            load_and_clean_dataset(conflict_csv)

    def test_custom_dataset_uses_non_dummy_disclaimer(
        self,
        ai_service_root: Path,
        tmp_path: Path,
    ) -> None:
        src_csv = ai_service_root / "data" / "intent_dataset_dummy.csv"
        custom_csv = tmp_path / "ds04_final_dataset.csv"
        custom_csv.write_text(src_csv.read_text(encoding="utf-8"), encoding="utf-8")

        report = run_training_pipeline(
            dataset_path=custom_csv,
            output_model_path=tmp_path / "model.joblib",
            output_report_path=tmp_path / "report.json",
        )
        assert "Dataset kustom/handoff" in report["dataset_disclaimer"]
        assert "sebelum handoff dataset final DS-04" not in report["dataset_disclaimer"]
