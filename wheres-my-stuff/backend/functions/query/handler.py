"""'Where is X' search Lambda.

Resolves a natural-language item query against the inventory and returns ranked
matches with a full location breadcrumb. Matching is synonym-aware using the same
shared/synonyms.json the eval harness uses, so "wire nuts" finds an item labeled
"wire connectors".

The DynamoDB/AppSync fetch is injected (``item_source``) so ``rank_matches`` stays
pure and unit-testable. ``lambda_handler`` wires in the real source.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

_WORD_RE = re.compile(r"[^a-z0-9 ]+")
_STOPWORDS = {"where", "are", "is", "my", "the", "a", "an", "do", "i", "have", "find", "get"}


def normalize(term: str) -> str:
    t = _WORD_RE.sub(" ", (term or "").lower())
    out = []
    for w in t.split():
        if len(w) > 3 and w.endswith("es") and w[:-2].endswith(("s", "x", "z", "ch", "sh")):
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return " ".join(out)


class SynonymMatcher:
    def __init__(self, groups: list[list[str]]):
        self._term_to_group: dict[str, int] = {}
        for gid, group in enumerate(groups):
            for term in group:
                self._term_to_group[normalize(term)] = gid

    @classmethod
    def load(cls, path: str | None = None) -> "SynonymMatcher":
        # shared/synonyms.json is the single source of truth (bundled at deploy).
        default = Path(__file__).resolve().parents[3] / "shared" / "synonyms.json"
        data = json.loads(Path(path or os.environ.get("SYNONYMS_PATH", default)).read_text())
        return cls(data.get("groups", []))

    def expand(self, term: str) -> set[str]:
        """All normalized terms equivalent to ``term`` (itself + its group)."""
        n = normalize(term)
        terms = {n}
        gid = self._term_to_group.get(n)
        if gid is not None:
            terms |= {t for t, g in self._term_to_group.items() if g == gid}
        return terms


def _query_terms(query: str) -> list[str]:
    return [w for w in normalize(query).split() if w not in _STOPWORDS]


def _score(item: dict, query_terms: list[str], matcher: SynonymMatcher) -> float:
    """Weighted overlap of expanded query terms against name/tags/OCR text."""
    name_tokens = set(normalize(item.get("name", "")).split())
    tag_tokens = {t for tag in item.get("tags", []) for t in normalize(tag).split()}
    ocr_tokens = set(normalize(item.get("ocrText", "")).split())

    score = 0.0
    for term in query_terms:
        variants = matcher.expand(term)
        if name_tokens & variants:
            score += 3.0
        elif tag_tokens & variants:
            score += 1.5
        elif ocr_tokens & variants:
            score += 1.0
    return score / max(1, len(query_terms))


def breadcrumb(item: dict, locations_by_id: dict[str, dict]) -> str:
    """Walk parent links to build 'Garage > Wall shelf B > Bin 3'."""
    parts: list[str] = []
    loc = locations_by_id.get(item.get("locationId"))
    seen = set()
    while loc and loc.get("id") not in seen:
        seen.add(loc.get("id"))
        parts.append(loc.get("name", "?"))
        loc = locations_by_id.get(loc.get("parentId"))
    return " > ".join(reversed(parts))


def rank_matches(
    query: str,
    items: list[dict],
    locations_by_id: dict[str, dict],
    matcher: SynonymMatcher,
    limit: int = 5,
) -> list[dict]:
    terms = _query_terms(query)
    scored = []
    for item in items:
        s = _score(item, terms, matcher)
        if s > 0:
            scored.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "quantity": item.get("quantity"),
                "score": round(s, 3),
                "location": breadcrumb(item, locations_by_id),
                "primaryPhotoId": item.get("primaryPhotoId"),
            })
    scored.sort(key=lambda m: m["score"], reverse=True)
    return scored[:limit]


def lambda_handler(event, _context=None):  # pragma: no cover - thin AWS glue
    query = (event or {}).get("arguments", {}).get("query", "")
    matcher = SynonymMatcher.load()
    items, locations_by_id = _fetch_inventory()
    return rank_matches(query, items, locations_by_id, matcher)


def _fetch_inventory():  # pragma: no cover - replaced by AppSync/DynamoDB access
    """Return (items, {locationId: location}). Stubbed; wire to AppSync/DynamoDB."""
    return [], {}
