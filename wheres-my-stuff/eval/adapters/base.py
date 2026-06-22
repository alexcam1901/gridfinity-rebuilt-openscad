"""Adapter interface shared by every candidate."""
from __future__ import annotations

import time
from dataclasses import dataclass

from ..schema import Prediction, Usage


@dataclass
class PredictResult:
    prediction: Prediction
    usage: Usage
    latency_s: float


class Adapter:
    """Base class. ``model_name`` must match a key in ``pricing.PRICING``."""

    model_name: str = "unknown"

    def _predict(self, image_path: str) -> tuple[Prediction, Usage]:
        raise NotImplementedError

    def predict(self, image_path: str) -> PredictResult:
        start = time.perf_counter()
        prediction, usage = self._predict(image_path)
        return PredictResult(prediction, usage, time.perf_counter() - start)
