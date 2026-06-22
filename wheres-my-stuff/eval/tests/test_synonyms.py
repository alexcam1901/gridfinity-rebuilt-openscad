from eval.synonyms import SynonymMap, normalize


def test_normalize_depluralizes_and_strips():
    assert normalize("Wire Nuts!") == "wire nut"
    assert normalize("  CABLE   TIES ") == "cable tie"
    assert normalize("boxes") == "box"


def test_synonym_equivalence_uses_shared_map():
    syn = SynonymMap.load()  # loads shared/synonyms.json
    assert syn.equivalent("wire nuts", "wire connectors")
    assert syn.equivalent("zip ties", "cable ties")
    assert not syn.equivalent("wire nuts", "zip ties")


def test_exact_match_without_group():
    syn = SynonymMap([])
    assert syn.equivalent("widget", "widgets")  # normalization handles plural
    assert not syn.equivalent("widget", "gadget")
