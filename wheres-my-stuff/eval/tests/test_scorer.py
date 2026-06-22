from eval.schema import GoldItem, Prediction, Usage
from eval.scorer import aggregate, score_item
from eval.synonyms import SynonymMap

SYN = SynonymMap.load()


def _gold(**kw):
    base = dict(id="x", image="x.jpg", name="wire nuts",
                tags=["electrical", "connectors", "red"], ocr_text="WIRE CONNECTORS")
    base.update(kw)
    return GoldItem.from_dict(base)


def test_name_correct_via_synonym():
    s = score_item(Prediction(name="wire connectors"), _gold(), SYN, 0.1, Usage(), "stub")
    assert s.name_correct is True


def test_name_incorrect():
    s = score_item(Prediction(name="zip ties"), _gold(), SYN, 0.1, Usage(), "stub")
    assert s.name_correct is False


def test_tag_precision_recall():
    pred = Prediction(name="wire nuts", tags=["electrical", "connectors", "blue"])
    s = score_item(pred, _gold(), SYN, 0.1, Usage(), "stub")
    assert round(s.tag_precision, 3) == round(2 / 3, 3)
    assert round(s.tag_recall, 3) == round(2 / 3, 3)


def test_ocr_recall_none_when_gold_empty():
    s = score_item(Prediction(ocr_text="anything"), _gold(ocr_text=""), SYN, 0.1, Usage(), "stub")
    assert s.ocr_recall is None


def test_ocr_recall_full():
    s = score_item(Prediction(ocr_text="wire connectors 100 pack"), _gold(), SYN, 0.1, Usage(), "stub")
    assert s.ocr_recall == 1.0


def test_cost_from_pricing():
    # haiku: $1/Mtok in, $5/Mtok out
    s = score_item(Prediction(name="wire nuts"), _gold(), SYN, 0.1,
                   Usage(input_tokens=1_000_000, output_tokens=1_000_000), "claude-haiku-4-5")
    assert round(s.cost_usd, 4) == 6.0


def test_aggregate_percentiles_and_means():
    scores = [
        score_item(Prediction(name="wire nuts"), _gold(), SYN, 0.1, Usage(), "stub"),
        score_item(Prediction(name="zip ties"), _gold(), SYN, 0.3, Usage(), "stub"),
    ]
    card = aggregate("stub", scores)
    assert card.n == 2
    assert card.name_accuracy == 0.5
    assert card.latency_p50 in (0.1, 0.3)
    assert card.latency_p95 == 0.3
