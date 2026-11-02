"""ML fallback for merchants the keyword rules don't know (categorizer layer 3).

TF-IDF over character n-grams + logistic regression, trained offline by `app.ml.train` and
loaded once per process. Predictions are only used at >= 0.6 confidence.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

MODEL_PATH = Path(__file__).parent / "model.joblib"
MIN_CONFIDENCE = 0.6

_DIGITS = re.compile(r"\d+")
_VPA = re.compile(r"[\w.\-]+@[\w.\-]+")  # not \S: narrations join fields with "/"
_MASKED = re.compile(r"[x*]{3,}\w*", re.IGNORECASE)
_NOISE = re.compile(r"\b(upi|dr|cr|neft|imps|pos|ach|payment|pay|ref|txn)\b")
# UPI-app phrasing ("Paid to X") carries no category signal, and "paid" would otherwise look
# like "prepaid"/"postpaid" (Mobile & Internet) to a character-n-gram model.
_APP_PHRASES = re.compile(
    r"\b(paid to|sent to|payment to|transfer to|money received from|received from|paid by)\b"
)
# The "don't know" label: person-to-person payments. Predicting it means "leave uncategorized".
ABSTAIN = "Other"


def clean_text(merchant: str, raw: str) -> str:
    """Merchant + narration, lowercased, with numbers, VPAs and masked cards removed.

    Only this anonymized text is ever used for training or prediction.
    """
    text = f"{merchant} {raw}".lower()
    text = _VPA.sub(" ", text)
    text = _MASKED.sub(" ", text)
    text = _DIGITS.sub(" ", text)
    text = _APP_PHRASES.sub(" ", text)
    text = re.sub(r"[^a-z&.' ]", " ", text)
    text = _NOISE.sub(" ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class Prediction:
    category_name: str
    confidence: float
    version: str


class CategoryModel:
    def __init__(self, pipeline: Any, version: str) -> None:
        self.pipeline = pipeline
        self.version = version

    def predict(self, merchant: str, raw: str) -> Prediction | None:
        text = clean_text(merchant, raw)
        if not text:
            return None
        probs = self.pipeline.predict_proba([text])[0]
        best = int(probs.argmax())
        return Prediction(str(self.pipeline.classes_[best]), float(probs[best]), self.version)

    def save(self, path: Path = MODEL_PATH) -> None:
        joblib.dump({"pipeline": self.pipeline, "version": self.version}, path)

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "CategoryModel | None":
        if not path.exists():
            return None
        data = joblib.load(path)
        return cls(data["pipeline"], data["version"])


@lru_cache(maxsize=1)
def get_model() -> CategoryModel | None:
    """The trained model, or None when none has been trained (the layer is then skipped)."""
    return CategoryModel.load()
