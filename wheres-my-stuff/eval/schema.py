"""Shared data shapes for gold items, predictions, and per-call usage."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Prediction:
    """A vision model's structured guess for one photo."""

    name: str = ""
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    ocr_text: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Prediction":
        return cls(
            name=str(d.get("name", "") or ""),
            category=d.get("category"),
            tags=[str(t) for t in (d.get("tags") or [])],
            ocr_text=str(d.get("ocr_text", "") or ""),
        )


@dataclass
class Usage:
    """Token / API-call accounting for one prediction, used to compute cost."""

    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0


@dataclass
class GoldItem:
    """One hand-labeled photo: the ground truth a candidate is scored against."""

    id: str
    image: str
    name: str
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    ocr_text: str = ""
    name_aliases: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "GoldItem":
        return cls(
            id=str(d["id"]),
            image=str(d["image"]),
            name=str(d["name"]),
            category=d.get("category"),
            tags=[str(t) for t in (d.get("tags") or [])],
            ocr_text=str(d.get("ocr_text", "") or ""),
            name_aliases=[str(a) for a in (d.get("name_aliases") or [])],
        )

    @property
    def accepted_names(self) -> list[str]:
        return [self.name, *self.name_aliases]


def load_gold(path: str | Path) -> list[GoldItem]:
    """Load a gold set from a JSONL file (one JSON object per line)."""
    items: list[GoldItem] = []
    for lineno, raw in enumerate(Path(path).read_text().splitlines(), start=1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            items.append(GoldItem.from_dict(json.loads(raw)))
        except (json.JSONDecodeError, KeyError) as exc:
            raise ValueError(f"{path}:{lineno}: invalid gold entry: {exc}") from exc
    return items
