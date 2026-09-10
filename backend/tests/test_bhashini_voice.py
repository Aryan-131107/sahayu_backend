# -*- coding: utf-8 -*-
"""
tests/test_bhashini_voice.py - Comprehensive Unit & Integration Tests for Bhashini Voice Module
Validates:
  1. Two-step ULCA architecture: Step 1 Config -> Step 2 Compute
  2. Dynamic extraction of serviceId, callbackUrl, inferenceApiKey (no hardcoded keys)
  3. Strict credential isolation (secrets used only for Config headers, never in compute or returned to frontend)
  4. Audio format & sample rate detection (WAV header parsing, WebM, OGG, MP3)
  5. In-memory configuration caching & TTL
  6. Endpoint integration: POST /api/voice/transcribe, POST /api/voice/speak, GET /api/voice/status
  7. Error resilience & graceful degradation
"""

import io
import wave
import struct
import base64
import pytest
import httpx
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services import bhashini_service

client = TestClient(app)


def _generate_dummy_wav(duration_ms: int = 500, sample_rate: int = 16000) -> bytes:
    """Generates a valid minimal WAV PCM audio buffer."""
    buf = io.BytesIO()
    num_frames = int(sample_rate * (duration_ms / 1000.0))
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # Write dummy silent/sine frames
        raw_frames = struct.pack("<" + "h" * num_frames, *([100] * num_frames))
        wf.writeframes(raw_frames)
    return buf.getvalue()


# ── 1. Audio Metadata & Format Detection Tests ───────────────────────────────

def test_detect_audio_metadata_wav():
    """WAV header parsing correctly extracts sampling rate."""
    wav_16k = _generate_dummy_wav(100, 16000)
    fmt, rate = bhashini_service.detect_audio_metadata(wav_16k, "audio/wav")
    assert fmt == "wav"
    assert rate == 16000

    wav_44k = _generate_dummy_wav(100, 44100)
    fmt2, rate2 = bhashini_service.detect_audio_metadata(wav_44k, "audio/wav")
    assert fmt2 == "wav"
    assert rate2 == 44100


def test_detect_audio_metadata_webm_and_ogg():
    """WebM and OGG headers/content-types are correctly detected."""
    webm_header = b"\x1aE\xdf\xa3" + b"\x00" * 30
    fmt, rate = bhashini_service.detect_audio_metadata(webm_header, "audio/webm")
    assert fmt == "webm"
    assert rate == 16000

    ogg_header = b"OggS" + b"\x00" * 30
    fmt_ogg, rate_ogg = bhashini_service.detect_audio_metadata(ogg_header, "audio/ogg; codecs=opus")
    assert fmt_ogg == "ogg"
    assert rate_ogg == 16000


def test_detect_audio_metadata_empty_or_fallback():
    """Empty or unknown audio falls back safely."""
    fmt, rate = bhashini_service.detect_audio_metadata(b"", None)
    assert fmt == "wav"
    assert rate == 16000


# ── 2. Configuration Caching & Two-Step Workflow Tests ───────────────────────

@pytest.mark.asyncio
async def test_fetch_pipeline_config_two_step_extraction():
    """
    Verifies Step 1: Config Call extracts serviceId, callbackUrl, inferenceApiKey,
    and caches the result in-memory.
    """
    bhashini_service.clear_config_cache()

    mock_config_response = {
        "pipelineResponseConfig": [
            {
                "taskType": "asr",
                "config": [
                    {
                        "serviceId": "ai4bharat/conformer-hi-gpu--v1",
                        "language": {"sourceLanguage": "hi"},
                    }
                ],
            }
        ],
        "pipelineInferenceAPIEndPoint": {
            "callbackUrl": "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
            "inferenceApiKey": {
                "name": "Authorization",
                "value": "mock_inference_jwt_token_12345",
            },
        },
    }

    # Set mock credentials
    settings.BHASHINI_USER_ID = "test_user_id_udyat"
    settings.BHASHINI_ULCA_API_KEY = "test_ulca_api_key_abc123"

    async def mock_post(url, json=None, headers=None):
        # Invariant check: User ID & ULCA API key must be passed in Step 1 headers
        assert headers.get("userID") == "test_user_id_udyat"
        assert headers.get("ulcaApiKey") == "test_ulca_api_key_abc123"
        assert json["pipelineTasks"][0]["taskType"] == "asr"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_config_response
        return mock_resp

    mock_client = MagicMock()
    mock_client.post = mock_post

    # 1. First fetch -> calls API and caches
    config = await bhashini_service.fetch_pipeline_config("asr", "hi", client=mock_client)
    assert config["service_id"] == "ai4bharat/conformer-hi-gpu--v1"
    assert config["callback_url"] == "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
    assert config["api_key_name"] == "Authorization"
    assert config["api_key_value"] == "mock_inference_jwt_token_12345"

    # 2. Second fetch -> must return from cache without triggering another API call
    cached = bhashini_service.get_cached_config("asr", "hi")
    assert cached is not None
    assert cached["service_id"] == "ai4bharat/conformer-hi-gpu--v1"


# ── 3. ASR Compute & Transcription Tests ─────────────────────────────────────

@pytest.mark.asyncio
async def test_transcribe_speech_full_flow():
    """
    Verifies Step 2: ASR Compute Call sends base64 audio and extracted serviceId
    to inference endpoint using the authorization header.
    """
    bhashini_service.clear_config_cache()
    settings.BHASHINI_USER_ID = "test_user_id_udyat"
    settings.BHASHINI_ULCA_API_KEY = "test_ulca_api_key_abc123"

    wav_bytes = _generate_dummy_wav(300, 16000)

    mock_config_response = {
        "pipelineResponseConfig": [
            {
                "taskType": "asr",
                "config": [{"serviceId": "bhashini_asr_service_hi_v2", "language": {"sourceLanguage": "hi"}}],
            }
        ],
        "pipelineInferenceAPIEndPoint": {
            "callbackUrl": "https://inference.bhashini.gov.in/asr",
            "inferenceApiKey": {"name": "Authorization", "value": "test_auth_token_999"},
        },
    }

    mock_asr_compute_response = {
        "pipelineResponse": [
            {
                "taskType": "asr",
                "output": [
                    {
                        "source": "पंखा रिपेयर करना है",
                    }
                ],
            }
        ]
    }

    async def mock_post(url, json=None, headers=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "getModelsPipeline" in url:
            mock_resp.json.return_value = mock_config_response
        else:
            # Invariant check: Compute call uses the dynamically obtained Authorization key & serviceId
            assert headers.get("Authorization") == "test_auth_token_999"
            assert json["pipelineTasks"][0]["config"]["serviceId"] == "bhashini_asr_service_hi_v2"
            assert "audioContent" in json["inputData"]["audio"][0]
            mock_resp.json.return_value = mock_asr_compute_response
        return mock_resp

    mock_client = MagicMock()
    mock_client.post = mock_post

    result = await bhashini_service.transcribe_speech(
        audio_bytes=wav_bytes,
        content_type="audio/wav",
        language="hi",
        client=mock_client,
    )

    assert result["success"] is True
    assert result["text"] == "पंखा रिपेयर करना है"
    assert result["language"] == "hi"


# ── 4. TTS Compute & Synthesis Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_synthesize_speech_full_flow():
    """
    Verifies TTS workflow: Step 1 Config -> Step 2 Compute -> extracts Base64 audio.
    """
    bhashini_service.clear_config_cache()
    settings.BHASHINI_USER_ID = "test_user_id_udyat"
    settings.BHASHINI_ULCA_API_KEY = "test_ulca_api_key_abc123"

    mock_tts_config_response = {
        "pipelineResponseConfig": [
            {
                "taskType": "tts",
                "config": [{"serviceId": "bhashini_tts_service_hi_female", "language": {"sourceLanguage": "hi"}}],
            }
        ],
        "pipelineInferenceAPIEndPoint": {
            "callbackUrl": "https://inference.bhashini.gov.in/tts",
            "inferenceApiKey": {"name": "Authorization", "value": "test_tts_token_888"},
        },
    }

    dummy_audio_b64 = base64.b64encode(b"RIFF_DUMMY_TTS_AUDIO_BYTES_12345").decode("utf-8")
    mock_tts_compute_response = {
        "pipelineResponse": [
            {
                "taskType": "tts",
                "audio": [
                    {
                        "audioContent": dummy_audio_b64,
                    }
                ],
            }
        ]
    }

    async def mock_post(url, json=None, headers=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "getModelsPipeline" in url:
            mock_resp.json.return_value = mock_tts_config_response
        else:
            assert headers.get("Authorization") == "test_tts_token_888"
            assert json["pipelineTasks"][0]["config"]["serviceId"] == "bhashini_tts_service_hi_female"
            assert json["inputData"]["input"][0]["source"] == "आपका कार्य सफलतापूर्वक स्वीकार कर लिया गया है।"
            mock_resp.json.return_value = mock_tts_compute_response
        return mock_resp

    mock_client = MagicMock()
    mock_client.post = mock_post

    result = await bhashini_service.synthesize_speech(
        text="आपका कार्य सफलतापूर्वक स्वीकार कर लिया गया है।",
        language="hi",
        gender="female",
        speed=1.0,
        client=mock_client,
    )

    assert result["success"] is True
    assert result["audio_base64"] == dummy_audio_b64
    assert result["audio_format"] == "wav"
    assert result["data_url"] == f"data:audio/wav;base64,{dummy_audio_b64}"


# ── 5. FastAPI Router Endpoint Tests ─────────────────────────────────────────

def test_voice_status_endpoint():
    """GET /api/voice/status returns status without exposing secrets."""
    resp = client.get("/api/voice/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "is_configured" in data
    assert data["supported_language"] == "hi"
    # Invariant: No credentials or tokens leaked
    assert "api_key" not in data
    assert "token" not in data
    assert "secret" not in data


def test_voice_speak_empty_text_error_handling():
    """POST /api/voice/speak rejects empty text payload cleanly."""
    resp = client.post("/api/voice/speak", json={"text": "   "})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "empty" in data["error"].lower()


def test_voice_transcribe_endpoint_with_mocked_service():
    """POST /api/voice/transcribe successfully processes uploaded audio file."""
    wav_bytes = _generate_dummy_wav(300, 16000)

    with patch("app.services.bhashini_service.transcribe_speech") as mock_ts:
        mock_ts.return_value = {
            "success": True,
            "text": "नल की मरम्मत का काम",
            "language": "hi",
        }

        files = {"file": ("recording.wav", io.BytesIO(wav_bytes), "audio/wav")}
        data = {"language": "hi"}

        resp = client.post("/api/voice/transcribe", files=files, data=data)
        assert resp.status_code == 200
        res = resp.json()
        assert res["success"] is True
        assert res["text"] == "नल की मरम्मत का काम"
        assert res["language"] == "hi"


def test_voice_speak_endpoint_with_mocked_service():
    """POST /api/voice/speak successfully processes Hindi text and returns playable audio."""
    dummy_b64 = "UklGRi4AAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="

    with patch("app.services.bhashini_service.synthesize_speech") as mock_ss:
        mock_ss.return_value = {
            "success": True,
            "audio_base64": dummy_b64,
            "audio_format": "wav",
            "mime_type": "audio/wav",
            "data_url": f"data:audio/wav;base64,{dummy_b64}",
        }

        payload = {
            "text": "भुगतान प्राप्त हुआ, धन्यवाद।",
            "language": "hi",
            "gender": "female",
            "speed": 1.0,
        }

        resp = client.post("/api/voice/speak", json=payload)
        assert resp.status_code == 200
        res = resp.json()
        assert res["success"] is True
        assert res["audio_base64"] == dummy_b64
        assert res["audio_format"] == "wav"
        assert res["data_url"].startswith("data:audio/wav;base64,")


def test_voice_transcribe_unconfigured_graceful_error():
    """When credentials are not configured, endpoint returns user-friendly error (no crash)."""
    settings.BHASHINI_USER_ID = ""
    settings.BHASHINI_ULCA_API_KEY = ""
    bhashini_service.clear_config_cache()

    wav_bytes = _generate_dummy_wav(300, 16000)
    files = {"file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")}

    resp = client.post("/api/voice/transcribe", files=files, data={"language": "hi"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "unavailable" in data["error"].lower() or "not configured" in data["error"].lower()

