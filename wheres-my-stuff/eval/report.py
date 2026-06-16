"""Render scorecards as a Markdown table and a CSV."""
from __future__ import annotations

import csv
import io

from .scorer import ModelScorecard


def _fmt(value: float | None, pct: bool = False, money: bool = False) -> str:
    if value is None:
        return "n/a"
    if money:
        return f"${value:.4f}"
    if pct:
        return f"{value * 100:.1f}%"
    return f"{value:.3f}"


def to_markdown(cards: list[ModelScorecard]) -> str:
    header = (
        "| Model | n | Name acc | Tag P | Tag R | Tag F1 | OCR recall | $/photo | p50 (s) | p95 (s) |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for c in sorted(cards, key=lambda x: x.name_accuracy, reverse=True):
        rows.append(
            f"| {c.model} | {c.n} | {_fmt(c.name_accuracy, pct=True)} | "
            f"{_fmt(c.tag_precision, pct=True)} | {_fmt(c.tag_recall, pct=True)} | "
            f"{_fmt(c.tag_f1, pct=True)} | {_fmt(c.ocr_recall, pct=True)} | "
            f"{_fmt(c.cost_per_photo, money=True)} | {_fmt(c.latency_p50)} | {_fmt(c.latency_p95)} |"
        )
    return "# Vision model scorecard\n\n" + header + "\n".join(rows) + "\n"


def to_csv(cards: list[ModelScorecard]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["model", "n", "name_accuracy", "tag_precision", "tag_recall", "tag_f1",
         "ocr_recall", "cost_per_photo", "latency_p50", "latency_p95"]
    )
    for c in sorted(cards, key=lambda x: x.name_accuracy, reverse=True):
        writer.writerow([
            c.model, c.n, round(c.name_accuracy, 4), round(c.tag_precision, 4),
            round(c.tag_recall, 4), round(c.tag_f1, 4),
            "" if c.ocr_recall is None else round(c.ocr_recall, 4),
            "" if c.cost_per_photo is None else round(c.cost_per_photo, 6),
            round(c.latency_p50, 4), round(c.latency_p95, 4),
        ])
    return buf.getvalue()
