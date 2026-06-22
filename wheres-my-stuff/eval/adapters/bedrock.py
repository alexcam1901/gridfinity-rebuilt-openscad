"""Bedrock adapter for Claude (Haiku/Sonnet) and Amazon Nova, one shared prompt.

Model IDs are env-overridable so you can pin region-specific inference profiles
without code changes (e.g. ``EVAL_HAIKU_MODEL_ID=us.anthropic.claude-haiku-4-5-...``).
"""
from __future__ import annotations

import base64
import json
import os

from ..prompt import PROMPT, parse_json_object
from ..schema import Prediction, Usage
from .base import Adapter

# model_key -> (family, pricing name, default Bedrock model id, env override var)
_MODELS = {
    "haiku": ("claude", "claude-haiku-4-5", "anthropic.claude-haiku-4-5", "EVAL_HAIKU_MODEL_ID"),
    "sonnet": ("claude", "claude-sonnet-4-6", "anthropic.claude-sonnet-4-6", "EVAL_SONNET_MODEL_ID"),
    "nova": ("nova", "nova-2-lite", "amazon.nova-2-lite-v1:0", "EVAL_NOVA_MODEL_ID"),
}

_MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_NOVA_FMT = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}


class BedrockAdapter(Adapter):
    def __init__(self, model_key: str, max_tokens: int = 512, region: str | None = None):
        if model_key not in _MODELS:
            raise ValueError(f"unknown bedrock model_key {model_key!r}")
        self.family, self.model_name, default_id, env_var = _MODELS[model_key]
        self.model_id = os.environ.get(env_var, default_id)
        self.max_tokens = max_tokens
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._client = None

    def _runtime(self):
        if self._client is None:
            try:
                import boto3  # lazy: only needed for a live run
            except ImportError as exc:  # pragma: no cover - env-dependent
                raise RuntimeError(
                    "boto3 is required for live model calls: pip install -r eval/requirements.txt"
                ) from exc
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    @staticmethod
    def _read_b64(image_path: str) -> str:
        with open(image_path, "rb") as fh:
            return base64.standard_b64encode(fh.read()).decode("ascii")

    def _build_body(self, image_path: str) -> dict:
        ext = os.path.splitext(image_path)[1].lower()
        b64 = self._read_b64(image_path)
        if self.family == "claude":
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64",
                            "media_type": _MEDIA.get(ext, "image/jpeg"),
                            "data": b64,
                        }},
                        {"type": "text", "text": PROMPT},
                    ],
                }],
            }
        # Nova
        return {
            "messages": [{
                "role": "user",
                "content": [
                    {"image": {"format": _NOVA_FMT.get(ext, "jpeg"), "source": {"bytes": b64}}},
                    {"text": PROMPT},
                ],
            }],
            "inferenceConfig": {"maxTokens": self.max_tokens},
        }

    @staticmethod
    def _parse_claude(resp: dict) -> tuple[str, Usage]:
        text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
        u = resp.get("usage", {})
        return text, Usage(u.get("input_tokens", 0), u.get("output_tokens", 0), 1)

    @staticmethod
    def _parse_nova(resp: dict) -> tuple[str, Usage]:
        content = resp.get("output", {}).get("message", {}).get("content", [])
        text = "".join(b.get("text", "") for b in content if "text" in b)
        u = resp.get("usage", {})
        return text, Usage(u.get("inputTokens", 0), u.get("outputTokens", 0), 1)

    def _predict(self, image_path: str) -> tuple[Prediction, Usage]:
        body = self._build_body(image_path)
        resp = self._runtime().invoke_model(modelId=self.model_id, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
        text, usage = (self._parse_claude if self.family == "claude" else self._parse_nova)(payload)
        return Prediction.from_dict(parse_json_object(text)), usage
