"""Run the eval: candidates x gold set -> scorecard.

Examples:
    python -m eval.run_eval --models haiku,nova,rekognition
    python -m eval.run_eval --models stub --gold eval/tests/fixtures/gold.jsonl \
        --fixtures eval/tests/fixtures/stub_predictions.json

Gold entries whose image file is missing are skipped with a warning, so a fresh
checkout (no real photos yet) still runs structurally.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .adapters import AVAILABLE, build_adapter
from .report import to_csv, to_markdown
from .schema import load_gold
from .scorer import ModelScorecard, aggregate, score_item
from .synonyms import SynonymMap

_HERE = Path(__file__).resolve().parent


def _resolve_image(gold_image: str, gold_path: Path) -> Path:
    p = Path(gold_image)
    return p if p.is_absolute() else (gold_path.parent / p)


def run(
    models: list[str],
    gold_path: str,
    fixtures: dict | None = None,
    synonyms_path: str | None = None,
) -> list[ModelScorecard]:
    syn = SynonymMap.load(synonyms_path)
    gold = load_gold(gold_path)
    gold_path_obj = Path(gold_path)
    cards: list[ModelScorecard] = []

    for model in models:
        kwargs = {"fixtures": fixtures} if model == "stub" else {}
        adapter = build_adapter(model, **kwargs)
        scores = []
        for item in gold:
            image = _resolve_image(item.image, gold_path_obj)
            if model != "stub" and not image.exists():
                print(f"  skip {item.id}: missing image {image}", file=sys.stderr)
                continue
            result = adapter.predict(str(image))
            scores.append(
                score_item(result.prediction, item, syn, result.latency_s,
                           result.usage, adapter.model_name)
            )
        cards.append(aggregate(model, scores))
    return cards


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vision model eval harness")
    parser.add_argument("--models", default="haiku,sonnet,nova,rekognition",
                        help=f"comma-separated; any of {AVAILABLE}")
    parser.add_argument("--gold", default=str(_HERE / "gold.jsonl"))
    parser.add_argument("--fixtures", help="JSON file of stub predictions (stub model only)")
    parser.add_argument("--synonyms", help="path to synonyms.json (defaults to shared/)")
    parser.add_argument("--out-md", help="write Markdown scorecard here")
    parser.add_argument("--out-csv", help="write CSV scorecard here")
    args = parser.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    fixtures = json.loads(Path(args.fixtures).read_text()) if args.fixtures else None

    if not Path(args.gold).exists():
        print(f"gold set not found: {args.gold}\n"
              "Add labeled photos to eval/gold/ and entries to eval/gold.jsonl.",
              file=sys.stderr)
        return 2

    cards = run(models, args.gold, fixtures=fixtures, synonyms_path=args.synonyms)
    md = to_markdown(cards)
    print(md)
    if args.out_md:
        Path(args.out_md).write_text(md)
    if args.out_csv:
        Path(args.out_csv).write_text(to_csv(cards))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
