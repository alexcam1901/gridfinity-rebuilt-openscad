"""Voice clip → text Lambda using Amazon Transcribe.

Accepts an S3 key pointing to an audio recording (WAV/MP4/M4A/WebM accepted by
Transcribe), starts a transcription job, polls until done, and returns the
transcript text. The caller (Flutter via AppSync mutation `transcribeAudio`) then
routes the text to either:
  - the `query` Lambda ("where are my wire nuts?"), or
  - the item confirm-screen flow ("add ten AA batteries to kitchen drawer").

Job polling is fine for a personal-scale app where recordings are short (< 60 s).
For high-volume use, swap to an S3 event-triggered async approach.
"""
from __future__ import annotations

import os
import time
import uuid


def start_job(s3_uri: str, language_code: str, client) -> str:
    """Start a Transcribe job and return the job name."""
    job_name = f"wms-{uuid.uuid4().hex[:12]}"
    media_format = _format_from_uri(s3_uri)
    client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": s3_uri},
        MediaFormat=media_format,
        LanguageCode=language_code,
        Settings={"ShowSpeakerLabels": False},
    )
    return job_name


def poll_job(job_name: str, client, timeout: int = 120, interval: int = 3) -> str:
    """Poll until the job completes and return the transcript text URI."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get_transcription_job(TranscriptionJobName=job_name)
        status = resp["TranscriptionJob"]["TranscriptionJobStatus"]
        if status == "COMPLETED":
            return resp["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        if status == "FAILED":
            reason = resp["TranscriptionJob"].get("FailureReason", "unknown")
            raise RuntimeError(f"Transcribe job failed: {reason}")
        time.sleep(interval)
    raise TimeoutError(f"Transcribe job {job_name} timed out after {timeout}s")


def fetch_transcript(transcript_uri: str) -> str:
    """Download the Transcribe JSON result and return the transcript string."""
    import json
    import urllib.request

    with urllib.request.urlopen(transcript_uri) as f:  # noqa: S310 – internal AWS URL
        data = json.load(f)
    return data["results"]["transcripts"][0]["transcript"]


def _format_from_uri(uri: str) -> str:
    ext = uri.rsplit(".", 1)[-1].lower()
    return {"mp4": "mp4", "m4a": "mp4", "wav": "wav", "webm": "webm",
            "ogg": "ogg", "flac": "flac"}.get(ext, "mp4")


def transcribe_s3(
    s3_uri: str,
    language_code: str = "en-US",
    client=None,
    _poll_fn=None,
    _fetch_fn=None,
) -> str:
    """Transcribe an S3 audio file and return plain text. Dependencies injected for testing."""
    if client is None:  # pragma: no cover — real AWS call
        import boto3
        client = boto3.client("transcribe", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    poll = _poll_fn or poll_job
    fetch = _fetch_fn or fetch_transcript

    job_name = start_job(s3_uri, language_code, client)
    uri = poll(job_name, client)
    return fetch(uri)


def lambda_handler(event, _context=None):  # pragma: no cover — thin AWS glue
    """AppSync mutation handler: transcribeAudio(s3Key: String!): String"""
    s3_key = (event or {}).get("arguments", {}).get("s3Key", "")
    bucket = os.environ.get("AUDIO_BUCKET", "")
    if not s3_key or not bucket:
        raise ValueError("s3Key argument and AUDIO_BUCKET env var are required")
    s3_uri = f"s3://{bucket}/{s3_key}"
    return transcribe_s3(s3_uri)
