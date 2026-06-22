"""Rekognition adapter: DetectLabels + DetectText mapped into the shared schema.

This is the non-LLM baseline. It cannot produce a fine-grained item name on its
own, so ``name`` is the top label and the OCR text is surfaced separately — which
is exactly the gap the eval is meant to quantify.
"""
from __future__ import annotations

import os

from ..schema import Prediction, Usage
from .base import Adapter


class RekognitionAdapter(Adapter):
    model_name = "rekognition"

    def __init__(self, max_labels: int = 10, min_confidence: float = 55.0, region: str | None = None):
        self.max_labels = max_labels
        self.min_confidence = min_confidence
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._client = None

    def _rek(self):
        if self._client is None:
            try:
                import boto3  # lazy
            except ImportError as exc:  # pragma: no cover - env-dependent
                raise RuntimeError(
                    "boto3 is required for live model calls: pip install -r eval/requirements.txt"
                ) from exc
            self._client = boto3.client("rekognition", region_name=self.region)
        return self._client

    def _predict(self, image_path: str) -> tuple[Prediction, Usage]:
        with open(image_path, "rb") as fh:
            blob = fh.read()
        client = self._rek()

        labels_resp = client.detect_labels(
            Image={"Bytes": blob},
            MaxLabels=self.max_labels,
            MinConfidence=self.min_confidence,
        )
        labels = [lab["Name"].lower() for lab in labels_resp.get("Labels", [])]

        text_resp = client.detect_text(Image={"Bytes": blob})
        lines = [
            d["DetectedText"]
            for d in text_resp.get("TextDetections", [])
            if d.get("Type") == "LINE"
        ]
        ocr_text = " ".join(lines)

        pred = Prediction(
            name=labels[0] if labels else "",
            category=labels[1] if len(labels) > 1 else None,
            tags=labels[:8],
            ocr_text=ocr_text,
        )
        return pred, Usage(api_calls=2)  # DetectLabels + DetectText
