"""Intent classification service backed by scikit-learn joblib artifacts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib

from src.config import settings
from src.preprocessing import normalize_text
from src.schemas import VALID_INTENTS

logger = logging.getLogger(__name__)


class ModelNotLoadedError(RuntimeError):
    """Raised when intent prediction is requested without a loaded model."""


class IntentService:
    """Loads the trained intent classifier artifact and runs inference."""

    def __init__(self, model_path: Path | str | None = None) -> None:
        self.model_path = Path(model_path) if model_path is not None else settings.MODEL_PATH
        self.is_loaded: bool = False
        self.model_name: str | None = None
        self.pipeline: Any = None
        self.classes: list[str] = list(VALID_INTENTS)
        self.trained_at: str | None = None
        self.metrics: dict[str, Any] = {}

    def load(self) -> bool:
        """Load the joblib model artifact from disk.

        Returns True if loaded successfully, False otherwise.
        """
        if not self.model_path.exists():
            logger.warning("Intent model artifact not found at %s", self.model_path)
            self.is_loaded = False
            return False

        try:
            artifact = joblib.load(self.model_path)
            if not isinstance(artifact, dict) or "pipeline" not in artifact:
                raise ValueError("Format artefak model tidak valid (missing 'pipeline').")

            pipeline = artifact["pipeline"]
            if not hasattr(pipeline, "predict_proba"):
                raise ValueError("Pipeline model tidak mendukung predict_proba.")

            raw_classes = artifact.get("classes")
            if raw_classes is None and hasattr(pipeline, "classes_"):
                raw_classes = list(pipeline.classes_)
            if not raw_classes:
                raise ValueError("Daftar kelas intent pada artefak model kosong.")

            self.pipeline = pipeline
            self.classes = [str(label) for label in raw_classes]
            self.model_name = str(artifact.get("model_name", "unknown"))
            self.trained_at = artifact.get("trained_at")
            self.metrics = artifact.get("metrics") or {}
            self.is_loaded = True
            logger.info(
                "Loaded intent model '%s' from %s (classes=%s)",
                self.model_name,
                self.model_path,
                self.classes,
            )
            return True
        except Exception as exc:
            logger.exception("Failed to load intent model from %s: %s", self.model_path, exc)
            self.is_loaded = False
            self.pipeline = None
            return False

    def predict(self, message: str) -> dict[str, Any]:
        """Predict intent label and class probabilities for a customer message."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Pesan tidak boleh kosong atau bukan teks.")

        if not self.is_loaded or self.pipeline is None:
            if not self.load():
                raise ModelNotLoadedError(
                    "Model klasifikasi intent belum tersedia. Jalankan training terlebih dahulu."
                )

        normalized = normalize_text(message)
        if not normalized:
            fallback_scores = {
                label: (1.0 if label == "lainnya" else 0.0)
                for label in self.classes
            }
            if "lainnya" not in fallback_scores:
                fallback_scores["lainnya"] = 1.0
            sorted_scores = dict(
                sorted(fallback_scores.items(), key=lambda item: item[1], reverse=True)
            )
            return {
                "original_message": message,
                "normalized_message": "",
                "intent": "lainnya",
                "confidence": 1.0,
                "scores": sorted_scores,
            }

        raw_probs = self.pipeline.predict_proba([normalized])[0]
        if len(raw_probs) != len(self.classes):
            raise RuntimeError("Jumlah probabilitas model tidak sesuai dengan jumlah kelas.")

        paired = [
            (label, float(prob))
            for label, prob in zip(self.classes, raw_probs)
        ]
        paired.sort(key=lambda item: item[1], reverse=True)

        best_intent, best_prob = paired[0]
        scores = {label: round(prob, 4) for label, prob in paired}

        return {
            "original_message": message,
            "normalized_message": normalized,
            "intent": best_intent,
            "confidence": round(best_prob, 4),
            "scores": scores,
        }
