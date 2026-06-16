"""Tests for the transcribe Lambda — no AWS calls, all dependencies injected."""
from unittest.mock import MagicMock

import pytest

from backend.functions.transcribe.handler import (
    _format_from_uri,
    fetch_transcript,
    poll_job,
    start_job,
    transcribe_s3,
)


# ---------------------------------------------------------------------------
# _format_from_uri
# ---------------------------------------------------------------------------


def test_format_mp4():
    assert _format_from_uri("s3://bucket/rec.mp4") == "mp4"


def test_format_m4a_maps_to_mp4():
    assert _format_from_uri("s3://bucket/rec.m4a") == "mp4"


def test_format_wav():
    assert _format_from_uri("s3://bucket/rec.wav") == "wav"


def test_format_unknown_defaults_to_mp4():
    assert _format_from_uri("s3://bucket/rec.aac") == "mp4"


# ---------------------------------------------------------------------------
# start_job
# ---------------------------------------------------------------------------


def test_start_job_calls_transcribe():
    client = MagicMock()
    name = start_job("s3://b/clip.mp4", "en-US", client)
    assert name.startswith("wms-")
    client.start_transcription_job.assert_called_once()
    call_kwargs = client.start_transcription_job.call_args.kwargs
    assert call_kwargs["Media"] == {"MediaFileUri": "s3://b/clip.mp4"}
    assert call_kwargs["MediaFormat"] == "mp4"
    assert call_kwargs["LanguageCode"] == "en-US"


# ---------------------------------------------------------------------------
# poll_job
# ---------------------------------------------------------------------------


def _mock_client_sequence(*statuses):
    """Return a mock Transcribe client that cycles through ``statuses``."""
    client = MagicMock()
    responses = [
        {
            "TranscriptionJob": {
                "TranscriptionJobStatus": s,
                "Transcript": {"TranscriptFileUri": "https://example.com/out.json"},
            }
        }
        for s in statuses
    ]
    client.get_transcription_job.side_effect = responses
    return client


def test_poll_returns_uri_on_immediate_completion():
    client = _mock_client_sequence("COMPLETED")
    uri = poll_job("job1", client, timeout=10, interval=0)
    assert uri == "https://example.com/out.json"


def test_poll_waits_through_in_progress():
    client = _mock_client_sequence("IN_PROGRESS", "IN_PROGRESS", "COMPLETED")
    uri = poll_job("job1", client, timeout=10, interval=0)
    assert uri == "https://example.com/out.json"
    assert client.get_transcription_job.call_count == 3


def test_poll_raises_on_failure():
    client = MagicMock()
    client.get_transcription_job.return_value = {
        "TranscriptionJob": {
            "TranscriptionJobStatus": "FAILED",
            "FailureReason": "bad audio",
        }
    }
    with pytest.raises(RuntimeError, match="bad audio"):
        poll_job("job1", client, timeout=10, interval=0)


def test_poll_raises_on_timeout():
    import time

    client = MagicMock()
    client.get_transcription_job.return_value = {
        "TranscriptionJob": {"TranscriptionJobStatus": "IN_PROGRESS"}
    }
    start = time.time()
    with pytest.raises(TimeoutError):
        poll_job("job1", client, timeout=0, interval=0)
    assert time.time() - start < 2  # should exit immediately


# ---------------------------------------------------------------------------
# fetch_transcript
# ---------------------------------------------------------------------------


def test_fetch_transcript_parses_json(tmp_path):
    import json
    import urllib.request

    payload = {"results": {"transcripts": [{"transcript": "where are my wire nuts"}]}}
    path = tmp_path / "out.json"
    path.write_text(json.dumps(payload))

    original_urlopen = urllib.request.urlopen

    def fake_open(url):
        return open(path, "rb")  # noqa: SIM115

    urllib.request.urlopen = fake_open
    try:
        text = fetch_transcript("file:///ignored")
    finally:
        urllib.request.urlopen = original_urlopen

    assert text == "where are my wire nuts"


# ---------------------------------------------------------------------------
# transcribe_s3 integration (all injected)
# ---------------------------------------------------------------------------


def test_transcribe_s3_end_to_end():
    client = MagicMock()
    client.start_transcription_job.return_value = {}

    def fake_poll(job_name, c, **_):
        return "https://example.com/out.json"

    def fake_fetch(uri):
        return "drill bits half inch"

    result = transcribe_s3(
        "s3://bucket/audio.mp4",
        client=client,
        _poll_fn=fake_poll,
        _fetch_fn=fake_fetch,
    )
    assert result == "drill bits half inch"
