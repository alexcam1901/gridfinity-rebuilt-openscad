"""Candidate vision-model adapters, behind one interface.

Each adapter turns a photo into a :class:`~eval.schema.Prediction` plus timing and
usage. Heavy SDK deps (boto3) are imported lazily inside ``predict`` so the
package imports cleanly without AWS installed.
"""
from __future__ import annotations

from .base import Adapter, PredictResult

__all__ = ["Adapter", "PredictResult", "build_adapter", "AVAILABLE"]

# Names accepted on the CLI. Mapped to factory callables lazily to avoid importing
# boto3-backed modules unless actually requested.
AVAILABLE = ["haiku", "sonnet", "nova", "rekognition", "stub"]


def build_adapter(name: str, **kwargs) -> Adapter:
    if name == "stub":
        from .stub import StubAdapter

        return StubAdapter(**kwargs)
    if name in ("haiku", "sonnet", "nova"):
        from .bedrock import BedrockAdapter

        return BedrockAdapter(model_key=name, **kwargs)
    if name == "rekognition":
        from .rekognition import RekognitionAdapter

        return RekognitionAdapter(**kwargs)
    raise ValueError(f"unknown adapter {name!r}; choose from {AVAILABLE}")
