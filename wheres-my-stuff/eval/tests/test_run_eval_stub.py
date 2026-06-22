import json
from pathlib import Path

from eval.report import to_csv, to_markdown
from eval.run_eval import run

FIX = Path(__file__).parent / "fixtures"


def _fixtures():
    return json.loads((FIX / "stub_predictions.json").read_text())


def test_run_end_to_end_with_stub():
    cards = run(["stub"], str(FIX / "gold.jsonl"), fixtures=_fixtures())
    assert len(cards) == 1
    card = cards[0]
    assert card.n == 3
    # 2 of 3 names correct via synonyms (wire connectors, cable ties); screwdriver wrong.
    assert round(card.name_accuracy, 3) == round(2 / 3, 3)
    # OCR recall averages only the two items that have gold OCR text.
    assert card.ocr_recall == 1.0


def test_report_renders():
    cards = run(["stub"], str(FIX / "gold.jsonl"), fixtures=_fixtures())
    md = to_markdown(cards)
    assert "Vision model scorecard" in md
    assert "stub" in md
    csv_text = to_csv(cards)
    assert "name_accuracy" in csv_text.splitlines()[0]
