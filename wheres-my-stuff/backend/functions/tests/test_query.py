from backend.functions.query.handler import (
    SynonymMatcher,
    breadcrumb,
    rank_matches,
)

MATCHER = SynonymMatcher.load()  # shared/synonyms.json

LOCATIONS = {
    "garage": {"id": "garage", "name": "Garage", "parentId": None},
    "shelfB": {"id": "shelfB", "name": "Wall shelf B", "parentId": "garage"},
    "bin3": {"id": "bin3", "name": "Bin 3", "parentId": "shelfB"},
}

ITEMS = [
    {"id": "i1", "name": "wire connectors", "tags": ["electrical"], "ocrText": "WIRE CONNECTORS",
     "locationId": "bin3", "quantity": 100},
    {"id": "i2", "name": "cordless drill", "tags": ["20v", "dewalt"], "ocrText": "",
     "locationId": "shelfB", "quantity": 1},
    {"id": "i3", "name": "zip ties", "tags": ["cable", "fasteners"], "ocrText": "CABLE TIES",
     "locationId": "garage", "quantity": 200},
]


def test_synonym_query_finds_differently_named_item():
    # User asks "wire nuts"; item is labeled "wire connectors".
    results = rank_matches("where are my wire nuts", ITEMS, LOCATIONS, MATCHER)
    assert results
    assert results[0]["id"] == "i1"
    assert results[0]["location"] == "Garage > Wall shelf B > Bin 3"


def test_query_ranks_name_over_tag():
    results = rank_matches("drill", ITEMS, LOCATIONS, MATCHER)
    assert results[0]["id"] == "i2"


def test_no_match_returns_empty():
    assert rank_matches("kayak paddle", ITEMS, LOCATIONS, MATCHER) == []


def test_breadcrumb_walks_parents():
    assert breadcrumb(ITEMS[0], LOCATIONS) == "Garage > Wall shelf B > Bin 3"


def test_synonym_query_via_tag_path():
    # "cable ties" is a synonym of "zip ties"; also present as a tag.
    results = rank_matches("cable ties", ITEMS, LOCATIONS, MATCHER)
    assert results[0]["id"] == "i3"
