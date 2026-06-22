"""Offline adapter for tests and dry-runs — no network, no image files needed.

It returns predictions from an in-memory mapping keyed by the gold item's image
filename (or id). Used to exercise the runner, scorer, and report end-to-end in CI.
"""
from __future__ import annotations

import os

from ..schema import Prediction, Usage
from .base import Adapter


class StubAdapter(Adapter):
    model_name = "stub"

    def __init__(self, fixtures: dict[str, dict] | None = None):
        # key -> prediction dict. Key may be the image path, its basename, or id.
        self._fixtures = fixtures or {}

    def _lookup(self, image_path: str) -> dict:
        for key in (image_path, os.path.basename(image_path)):
            if key in self._fixtures:
                return self._fixtures[key]
        return {}

    def _predict(self, image_path: str) -> tuple[Prediction, Usage]:
        return Prediction.from_dict(self._lookup(image_path)), Usage(api_calls=1)
