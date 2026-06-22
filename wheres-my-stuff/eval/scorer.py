"""Score predictions against gold items, synonym-aware.

Per item: name correctness (exact-or-synonym vs any accepted name), tag
precision/recall/F1, and OCR recall (fraction of expected label tokens present).
Aggregates add mean cost and p50/p95 latency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from .pricing import cost_for
from .schema import GoldItem, Prediction, Usage
from .synonyms import SynonymMap, normalize


@dataclass
class ItemScore:
    id: str
    name_correct: bool
    tag_precision: float
    tag_recall: float
    tag_f1: float
    ocr_recall: float | None  # None when gold has no OCR text to check
    latency_s: float
    cost_usd: float | None


def _name_correct(pred: Prediction, gold: GoldItem, syn: SynonymMap) -> bool:
    return any(syn.equivalent(pred.name, accepted) for accepted in gold.accepted_names)


def _tag_scores(pred: Prediction, gold: GoldItem, syn: SynonymMap) -> tuple[float, float, float]:
    gold_tags = [t for t in gold.tags if t.strip()]
    pred_tags = [t for t in pred.tags if t.strip()]
    if not gold_tags and not pred_tags:
        return 1.0, 1.0, 1.0
    if not pred_tags:
        return 0.0, 0.0, 0.0
    if not gold_tags:
        return 0.0, 1.0, 0.0

    matched_pred = sum(1 for p in pred_tags if any(syn.equivalent(p, g) for g in gold_tags))
    matched_gold = sum(1 for g in gold_tags if any(syn.equivalent(g, p) for p in pred_tags))
    precision = matched_pred / len(pred_tags)
    recall = matched_gold / len(gold_tags)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _ocr_recall(pred: Prediction, gold: GoldItem) -> float | None:
    gold_tokens = set(normalize(gold.ocr_text).split())
    if not gold_tokens:
        return None
    pred_tokens = set(normalize(pred.ocr_text).split())
    return len(gold_tokens & pred_tokens) / len(gold_tokens)


def score_item(
    pred: Prediction,
    gold: GoldItem,
    syn: SynonymMap,
    latency_s: float,
    usage: Usage,
    model_name: str,
) -> ItemScore:
    precision, recall, f1 = _tag_scores(pred, gold, syn)
    return ItemScore(
        id=gold.id,
        name_correct=_name_correct(pred, gold, syn),
        tag_precision=precision,
        tag_recall=recall,
        tag_f1=f1,
        ocr_recall=_ocr_recall(pred, gold),
        latency_s=latency_s,
        cost_usd=cost_for(model_name, usage),
    )


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round((pct / 100) * (len(ordered) - 1))))
    return ordered[k]


@dataclass
class ModelScorecard:
    model: str
    n: int
    name_accuracy: float
    tag_precision: float
    tag_recall: float
    tag_f1: float
    ocr_recall: float | None
    cost_per_photo: float | None
    latency_p50: float
    latency_p95: float
    items: list[ItemScore] = field(default_factory=list)


def aggregate(model: str, scores: list[ItemScore]) -> ModelScorecard:
    if not scores:
        return ModelScorecard(model, 0, 0, 0, 0, 0, None, None, 0, 0)
    ocr_vals = [s.ocr_recall for s in scores if s.ocr_recall is not None]
    cost_vals = [s.cost_usd for s in scores if s.cost_usd is not None]
    latencies = [s.latency_s for s in scores]
    return ModelScorecard(
        model=model,
        n=len(scores),
        name_accuracy=mean(s.name_correct for s in scores),
        tag_precision=mean(s.tag_precision for s in scores),
        tag_recall=mean(s.tag_recall for s in scores),
        tag_f1=mean(s.tag_f1 for s in scores),
        ocr_recall=mean(ocr_vals) if ocr_vals else None,
        cost_per_photo=mean(cost_vals) if cost_vals else None,
        latency_p50=_percentile(latencies, 50),
        latency_p95=_percentile(latencies, 95),
        items=scores,
    )
