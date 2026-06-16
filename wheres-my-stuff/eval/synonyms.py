"""Synonym-aware term matching, shared by the eval scorer and the query Lambda.

Loads ``shared/synonyms.json`` (equivalence groups) and exposes normalization
plus an ``equivalent()`` check so "wire nuts" and "wire connectors" compare equal.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_DEFAULT_SYNONYMS = Path(__file__).resolve().parent.parent / "shared" / "synonyms.json"
_WORD_RE = re.compile(r"[^a-z0-9 ]+")


def normalize(term: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, and de-pluralize lightly."""
    t = _WORD_RE.sub(" ", (term or "").lower())
    words = []
    for w in t.split():
        if len(w) > 3 and w.endswith("es") and (
            w[:-2].endswith(("s", "x", "z", "ch", "sh"))
        ):
            w = w[:-2]  # sibilant plural: boxes -> box, watches -> watch
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]  # regular plural: ties -> tie, nuts -> nut
        words.append(w)
    return " ".join(words)


class SynonymMap:
    """Groups equivalent terms; ``equivalent(a, b)`` is normalize-or-same-group."""

    def __init__(self, groups: list[list[str]]):
        self._term_to_group: dict[str, int] = {}
        for gid, group in enumerate(groups):
            for term in group:
                self._term_to_group[normalize(term)] = gid

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SynonymMap":
        data = json.loads(Path(path or _DEFAULT_SYNONYMS).read_text())
        return cls(data.get("groups", []))

    def group_of(self, term: str) -> int | None:
        return self._term_to_group.get(normalize(term))

    def equivalent(self, a: str, b: str) -> bool:
        na, nb = normalize(a), normalize(b)
        if na and na == nb:
            return True
        ga, gb = self._term_to_group.get(na), self._term_to_group.get(nb)
        return ga is not None and ga == gb
