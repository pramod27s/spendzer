"""Train the category model. Run offline, never per request:

    python -m app.ml.train            # writes app/ml/model.joblib

Training data: the seeded keyword map (so a model exists from day one) plus every
rule-, override- and user-categorized spend across all users — as anonymized merchant text only.
Labels are system category names, so one model serves everyone.
"""

import asyncio
import random
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sqlalchemy import select

from app.core.db import SessionLocal
from app.ml.model import ABSTAIN, MODEL_PATH, CategoryModel, clean_text
from app.models import Category, Transaction
from app.models.enums import CategorizedBy, Direction, TxnKind

SEED = Path(__file__).resolve().parent.parent / "seed" / "merchant_keywords.yaml"
# Shapes keywords appear in on real statements, so seed samples look like real input.
_TEMPLATES = (
    "{kw}",
    "upi/dr/123456789012/{kw}/yesb/{kw}@ybl/payment",
    "pos 4591xxxxxxxx1234 {kw} in",
    "{kw} bangalore",
    "{kw} india pvt ltd",
)


# Synthetic person names (first + surname / initials) for the abstain class: paying a person
# says nothing about what the money was for, so the model should learn not to guess.
_FIRST = [
    # Common given names, plus family words people save contacts as.
    "ravi",
    "suresh",
    "ramesh",
    "mahesh",
    "ganesh",
    "praveen",
    "kiran",
    "arjun",
    "rahul",
    "rohit",
    "vikram",
    "anil",
    "sunil",
    "venkatesh",
    "harish",
    "raju",
    "shiva",
    "sanjay",
    "deepak",
    "vinay",
    "priya",
    "kavya",
    "divya",
    "pooja",
    "lakshmi",
    "sunita",
    "anitha",
    "meera",
    "sneha",
    "deepa",
    "asha",
    "rekha",
    "usha",
    "bhavya",
    "bhagyalakshmi",
    "chaitra",
    "ramya",
    "shruti",
    "akka",
    "amma",
    "appa",
    "anna",
    "maama",
    "chikkappa",
    "atte",
]
_LAST = [
    "kumar",
    "rao",
    "gowda",
    "reddy",
    "naik",
    "shetty",
    "sharma",
    "nair",
    "iyer",
    "patil",
    "s",
    "k",
    "g",
    "m",
    "b",
    "t",
    "r",
    "n",
    "hk",
    "mb",
    "kr",
]


def abstain_samples() -> list[tuple[str, str]]:
    rng = random.Random(11)
    names: list[str] = []
    for first in _FIRST:
        names.append(first)
        names.extend(f"{first} {last}" for last in rng.sample(_LAST, 4))
    return [(clean_text(n, f"Paid to {n.upper()}"), ABSTAIN) for n in names]


def seed_samples() -> list[tuple[str, str]]:
    """The bootstrap set: seeded keywords in realistic shapes, plus person-name payments."""
    with SEED.open(encoding="utf-8") as fh:
        keywords: dict[str, list[str]] = yaml.safe_load(fh)
    samples = []
    for category, words in keywords.items():
        for word in words:
            for template in _TEMPLATES:
                samples.append((clean_text("", template.format(kw=str(word).lower())), category))
    return samples + abstain_samples()


async def db_samples() -> list[tuple[str, str]]:
    stmt = (
        select(Transaction.merchant, Transaction.raw_description, Category.name)
        .join(Category, Category.id == Transaction.category_id)
        .where(
            Category.user_id.is_(None),  # system categories only: shared labels
            Category.name != "Other",
            Transaction.kind == TxnKind.EXPENSE,
            Transaction.direction == Direction.DEBIT,
            Transaction.categorized_by.in_(
                [CategorizedBy.RULE, CategorizedBy.OVERRIDE, CategorizedBy.USER]
            ),
        )
    )
    async with SessionLocal() as session:
        rows = (await session.execute(stmt)).all()
    return [(clean_text(m, r), name) for m, r, name in rows]


def train(samples: list[tuple[str, str]]) -> CategoryModel:
    samples = [(t, label) for t, label in samples if t]
    labels = Counter(label for _, label in samples)
    if len(labels) < 2:
        raise SystemExit("Need at least two categories with examples to train.")
    random.Random(7).shuffle(samples)
    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
            # Moderate C: confident on real merchant names, unsure on everything else.
            ("clf", LogisticRegression(C=5, max_iter=2000, class_weight="balanced")),
        ]
    )
    pipeline.fit([t for t, _ in samples], [label for _, label in samples])
    version = f"v{datetime.now(UTC):%Y%m%d%H%M}-n{len(samples)}"
    return CategoryModel(pipeline, version)


async def _main(out: Path) -> None:
    samples = seed_samples() + await db_samples()
    model = train(samples)
    model.save(out)
    print(f"Trained {model.version} -> {out}")


if __name__ == "__main__":
    import sys

    asyncio.run(_main(Path(sys.argv[1]) if len(sys.argv) > 1 else MODEL_PATH))
