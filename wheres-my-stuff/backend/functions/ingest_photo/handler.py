"""Photo-ingest Lambda: identify an item with Claude Haiku via Bedrock.

Triggered after a photo lands in S3. Calls the chosen vision model (default
Claude Haiku 4.5; ``VISION_MODEL_ID`` to override or swap to Nova) with the same
prompt the eval harness uses, and returns a structured {name, category, tags,
ocr_text} for the app's confirm screen. Optionally runs Rekognition DetectText
first as a cheap OCR pre-pass (``USE_REKOGNITION_OCR=1``).

The Bedrock/Rekognition/S3 clients are created lazily so the module imports
without boto3 (keeps unit tests fast and offline).
"""
from __future__ import annotations

import base64
import json
import os
import re

# Single source of truth for the prompt — mirrors eval/prompt.py so the model the
# eval picks behaves identically in production.
PROMPT = (
    "You are cataloging items for a home/garage inventory app. Identify the single "
    "main item in this photo as a person would name it when searching for it later "
    "(e.g. 'wire nuts', 'cordless drill', 'box of drywall screws').\n"
    "Respond with ONLY a JSON object, no prose, with these keys:\n"
    '  "name": short common name of the item\n'
    '  "category": a broad category (e.g. "electrical", "fasteners", "power tools")\n'
    '  "tags": 3-8 lowercase keywords someone might search by\n'
    '  "ocr_text": any text printed on packaging/labels, verbatim; "" if none\n'
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
DEFAULT_MODEL_ID = "anthropic.claude-haiku-4-5"


def parse_model_json(text: str) -> dict:
    """Extract the first JSON object from a model text response; {} on failure."""
    if not text:
        return {}
    m = _JSON_RE.search(text)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def build_claude_body(image_b64: str, media_type: str, max_tokens: int = 512) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": media_type, "data": image_b64,
                }},
                {"type": "text", "text": PROMPT},
            ],
        }],
    }


def normalize_result(parsed: dict) -> dict:
    """Coerce a model JSON object into the app's expected shape."""
    return {
        "name": str(parsed.get("name", "") or ""),
        "category": parsed.get("category"),
        "tags": [str(t) for t in (parsed.get("tags") or [])],
        "ocrText": str(parsed.get("ocr_text", "") or ""),
    }


def _media_type(key: str) -> str:
    ext = os.path.splitext(key)[1].lower()
    return {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")


def lambda_handler(event, _context=None):  # pragma: no cover - AWS glue
    bucket = event["bucket"]
    key = event["key"]
    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get("VISION_MODEL_ID", DEFAULT_MODEL_ID)

    import boto3  # lazy

    s3 = boto3.client("s3", region_name=region)
    image_bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()

    result: dict = {}
    if os.environ.get("USE_REKOGNITION_OCR") == "1":
        rek = boto3.client("rekognition", region_name=region)
        text_resp = rek.detect_text(Image={"Bytes": image_bytes})
        lines = [d["DetectedText"] for d in text_resp.get("TextDetections", [])
                 if d.get("Type") == "LINE"]
        result["rekText"] = " ".join(lines)

    bedrock = boto3.client("bedrock-runtime", region_name=region)
    body = build_claude_body(base64.standard_b64encode(image_bytes).decode("ascii"),
                             _media_type(key))
    resp = bedrock.invoke_model(modelId=model_id, body=json.dumps(body))
    payload = json.loads(resp["body"].read())
    text = "".join(b.get("text", "") for b in payload.get("content", [])
                   if b.get("type") == "text")

    result.update(normalize_result(parse_model_json(text)))
    result["modelUsed"] = "bedrock"
    result["modelName"] = model_id
    return result
