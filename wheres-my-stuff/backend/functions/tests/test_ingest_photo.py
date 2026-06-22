from backend.functions.ingest_photo.handler import (
    build_claude_body,
    normalize_result,
    parse_model_json,
)


def test_parse_plain_json():
    assert parse_model_json('{"name": "wire nuts", "tags": ["a"]}')["name"] == "wire nuts"


def test_parse_json_with_code_fence_and_prose():
    text = "Here you go:\n```json\n{\"name\": \"drill\", \"ocr_text\": \"DEWALT\"}\n```"
    parsed = parse_model_json(text)
    assert parsed["name"] == "drill"
    assert parsed["ocr_text"] == "DEWALT"


def test_parse_garbage_returns_empty():
    assert parse_model_json("no json here") == {}


def test_normalize_result_shape():
    out = normalize_result({"name": "zip ties", "tags": ["cable"], "ocr_text": "TIES"})
    assert out == {"name": "zip ties", "category": None, "tags": ["cable"], "ocrText": "TIES"}


def test_build_claude_body_structure():
    body = build_claude_body("BASE64DATA", "image/jpeg")
    assert body["anthropic_version"] == "bedrock-2023-05-31"
    content = body["messages"][0]["content"]
    assert content[0]["source"]["data"] == "BASE64DATA"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert "JSON object" in content[1]["text"]
