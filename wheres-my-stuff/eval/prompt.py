"""The single identification prompt + JSON parsing shared by all LLM adapters.

Using one prompt/schema across Claude and Nova keeps the eval comparison fair.
The same prompt is the basis for the production ``ingest-photo`` Lambda.
"""
from __future__ import annotations

import json
import re

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


def parse_json_object(text: str) -> dict:
    """Extract the first JSON object from a model's text response.

    Tolerates code fences and leading/trailing prose. Returns {} if nothing parses.
    """
    if not text:
        return {}
    match = _JSON_RE.search(text)
    if not match:
        return {}
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}
