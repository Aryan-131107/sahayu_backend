# -*- coding: utf-8 -*-
"""
app/services/bhashini_service.py - Bhashini AI Voice Assistance Service
Handles Hindi ASR (Speech-to-Text) and Hindi TTS (Text-to-Speech) using
the Bhashini / ULCA two-step pipeline architecture:
  1. Pipeline Config Call (uses User ID + ULCA API Key) -> returns serviceId & inference credentials
  2. Pipeline Compute Call (uses returned inference endpoint & authorization token)

Invariants:
- Zero credential exposure to frontend or persistent storage
- In-memory configuration caching for running backend instance
- Strict audio format & sample rate detection
- Graceful error isolation
"""

import os
import io
import time
import base64
import struct
import logging
from typing import Optional, Dict, Any, Tuple
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory pipeline configuration cache for running process
# Key: task_type (e.g. 'asr:hi', 'tts:hi') -> Config Dict
_PIPELINE_CONFIG_CACHE: Dict[str, Dict[str, Any]] = {}
_CONFIG_CACHE_TTL_SECONDS = 3600  # 1 hour


def clear_config_cache() -> None:
    """Clears the in-memory pipeline config cache (useful for testing or manual refresh)."""
    global _PIPELINE_CONFIG_CACHE
    _PIPELINE_CONFIG_CACHE.clear()


def is_configured() -> bool:
    """Check if Bhashini credentials are configured in backend environment."""
    user_id = (settings.BHASHINI_USER_ID or os.getenv("BHASHINI_USER_ID", "")).strip()
    ulca_key = (settings.BHASHINI_ULCA_API_KEY or os.getenv("BHASHINI_ULCA_API_KEY", "")).strip()
    return bool(user_id and ulca_key)


def get_cached_config(task_type: str, language: str = "hi") -> Optional[Dict[str, Any]]:
    """Retrieve cached pipeline configuration if present and not expired."""
    cache_key = f"{task_type}:{language}"
    entry = _PIPELINE_CONFIG_CACHE.get(cache_key)
    if entry:
        cached_at = entry.get("cached_at", 0)
        if time.time() - cached_at < _CONFIG_CACHE_TTL_SECONDS:
            return entry
    return None


def detect_audio_metadata(audio_bytes: bytes, content_type: Optional[str] = None) -> Tuple[str, int]:
    """
    Inspects magic bytes and MIME type to accurately determine audioFormat and samplingRate.
    Bhashini ASR requires exact format match (wav, webm, mp3, ogg, flac).
    """
    if not audio_bytes:
        return "wav", 16000

    header = audio_bytes[:32]
    ct = (content_type or "").lower().strip()

    # 1. WAV Format (RIFF....WAVE)
    if header.startswith(b"RIFF") and b"WAVE" in header[:16]:
        sample_rate = 16000
        try:
            # WAV fmt subchunk typically at byte 12..36
            fmt_pos = audio_bytes.find(b"fmt ", 12, 64)
            if fmt_pos != -1 and len(audio_bytes) >= fmt_pos + 16:
                rate = struct.unpack("<I", audio_bytes[fmt_pos + 12 : fmt_pos + 16])[0]
                if 8000 <= rate <= 48000:
                    sample_rate = rate
        except Exception:
            sample_rate = 16000
        return "wav", sample_rate

    # 2. WebM / Matroska (EBML header \x1aE\xdf\xa3)
    if header.startswith(b"\x1aE\xdf\xa3") or "webm" in ct:
        return "webm", 16000

    # 3. OGG / Opus / Vorbis (OggS)
    if header.startswith(b"OggS") or "ogg" in ct or "opus" in ct:
        return "ogg", 16000

    # 4. MP3 (ID3 tag or MPEG audio frame sync 0xFF 0xFB/0xF3/0xF2)
    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0) or "mp3" in ct or "mpeg" in ct:
        return "mp3", 44100

    # 5. FLAC (fLaC)
    if header.startswith(b"fLaC") or "flac" in ct:
        return "flac", 16000

    # 6. MP4 / M4A (ftyp)
    if b"ftyp" in header[:16] or "m4a" in ct or "mp4" in ct or "aac" in ct:
        return "wav", 16000

    # Default fallback based on content-type or wav
    if "webm" in ct:
        return "webm", 16000
    elif "ogg" in ct:
        return "ogg", 16000
    elif "mp3" in ct:
        return "mp3", 44100

    return "wav", 16000


async def fetch_pipeline_config(
    task_type: str,
    language: str = "hi",
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Step 1: Bhashini ULCA Pipeline Config Call.
    Requests pipeline configuration for the specified task ('asr' or 'tts') and language ('hi').
    Extracts serviceId, callbackUrl, and inferenceApiKey.
    Caches result in-memory.
    """
    user_id = (settings.BHASHINI_USER_ID or os.getenv("BHASHINI_USER_ID", "")).strip()
    ulca_key = (settings.BHASHINI_ULCA_API_KEY or os.getenv("BHASHINI_ULCA_API_KEY", "")).strip()
    pipeline_id = (settings.BHASHINI_PIPELINE_ID or os.getenv("BHASHINI_PIPELINE_ID", "64392f96daac500b55c543cd")).strip()
    config_url = (settings.BHASHINI_CONFIG_URL or "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline").strip()

    if not user_id or not ulca_key:
        raise ValueError("Bhashini AI credentials are not configured (BHASHINI_USER_ID or BHASHINI_ULCA_API_KEY missing).")

    # Check cache first
    cached = get_cached_config(task_type, language)
    if cached:
        return cached

    payload = {
        "pipelineTasks": [
            {
                "taskType": task_type,
                "config": {
                    "language": {
                        "sourceLanguage": language
                    }
                }
            }
        ],
        "pipelineRequestConfig": {
            "pipelineId": pipeline_id
        }
    }

    headers = {
        "Content-Type": "application/json",
        "userID": user_id,
        "ulcaApiKey": ulca_key,
    }

    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)
        should_close_client = True

    try:
        response = await client.post(config_url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error(f"Bhashini Pipeline Config failed with status {response.status_code}: {response.text}")
            raise RuntimeError(f"Bhashini Pipeline Config failed (HTTP {response.status_code}).")

        data = response.json()
    finally:
        if should_close_client:
            await client.aclose()

    # Parse response
    # 1. Inference endpoint & Authorization key
    inference_endpoint = data.get("pipelineInferenceAPIEndPoint", {})
    callback_url = inference_endpoint.get("callbackUrl")
    if not callback_url:
        raise RuntimeError("Bhashini Config response missing 'pipelineInferenceAPIEndPoint.callbackUrl'.")

    api_key_info = inference_endpoint.get("inferenceApiKey", {})
    api_key_name = api_key_info.get("name", "Authorization")
    api_key_value = api_key_info.get("value", "")

    if not api_key_value:
        raise RuntimeError("Bhashini Config response missing inference API authorization key value.")

    # 2. Extract serviceId for requested taskType and language
    service_id = None
    response_configs = data.get("pipelineResponseConfig", [])
    for task_cfg in response_configs:
        if task_cfg.get("taskType") == task_type:
            cfg_list = task_cfg.get("config", [])
            if isinstance(cfg_list, list):
                for item in cfg_list:
                    lang_info = item.get("language", {})
                    src_lang = lang_info.get("sourceLanguage") if isinstance(lang_info, dict) else None
                    if src_lang == language or not src_lang:
                        service_id = item.get("serviceId")
                        if service_id:
                            break
            elif isinstance(cfg_list, dict):
                service_id = cfg_list.get("serviceId")

            if not service_id and "serviceId" in task_cfg:
                service_id = task_cfg["serviceId"]

            if service_id:
                break

    if not service_id:
        raise RuntimeError(f"Could not resolve Bhashini serviceId for task '{task_type}' and language '{language}'.")

    config_result = {
        "task_type": task_type,
        "language": language,
        "service_id": service_id,
        "callback_url": callback_url,
        "api_key_name": api_key_name,
        "api_key_value": api_key_value,
        "cached_at": time.time(),
    }

    # Store in cache
    cache_key = f"{task_type}:{language}"
    _PIPELINE_CONFIG_CACHE[cache_key] = config_result
    logger.info(f"Successfully obtained & cached Bhashini {task_type.upper()} configuration (serviceId: {service_id}).")
    return config_result


async def transcribe_speech(
    audio_bytes: bytes,
    content_type: Optional[str] = None,
    language: str = "hi",
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Step 2: ASR Pipeline Compute Call.
    Converts audio bytes to base64, invokes Bhashini ASR inference endpoint, and extracts transcript.
    """
    if not audio_bytes or len(audio_bytes) < 100:
        return {
            "success": False,
            "error": "Audio payload is empty or invalid.",
        }

    # Max audio size limit: 10 MB
    if len(audio_bytes) > 10 * 1024 * 1024:
        return {
            "success": False,
            "error": "Audio file size exceeds 10MB limit.",
        }

    try:
        # Step 1: Config
        config = await fetch_pipeline_config("asr", language=language, client=client)
    except Exception as e:
        logger.error(f"Failed to fetch ASR config: {e}")
        return {
            "success": False,
            "error": "Voice recognition service configuration unavailable.",
        }

    audio_format, sampling_rate = detect_audio_metadata(audio_bytes, content_type)
    base64_audio = base64.b64encode(audio_bytes).decode("utf-8")

    compute_payload = {
        "pipelineTasks": [
            {
                "taskType": "asr",
                "config": {
                    "language": {
                        "sourceLanguage": language
                    },
                    "serviceId": config["service_id"],
                    "audioFormat": audio_format,
                    "samplingRate": sampling_rate
                }
            }
        ],
        "inputData": {
            "input": [
                {
                    "source": None
                }
            ],
            "audio": [
                {
                    "audioContent": base64_audio
                }
            ]
        }
    }

    inference_headers = {
        "Content-Type": "application/json",
        config["api_key_name"]: config["api_key_value"],
    }

    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=25.0)
        should_close_client = True

    try:
        response = await client.post(
            config["callback_url"],
            json=compute_payload,
            headers=inference_headers,
        )
        if response.status_code != 200:
            logger.error(f"Bhashini ASR compute failed with status {response.status_code}: {response.text}")
            return {
                "success": False,
                "error": "Speech transcription failed. Please speak clearly and try again.",
            }

        result = response.json()
    except Exception as e:
        logger.error(f"Error during ASR compute call: {e}")
        return {
            "success": False,
            "error": "Voice service request timed out or network error occurred.",
        }
    finally:
        if should_close_client:
            await client.aclose()

    # Extract recognized transcript
    transcript = ""
    try:
        pipeline_resp = result.get("pipelineResponse", [])
        for task in pipeline_resp:
            if task.get("taskType") == "asr":
                outputs = task.get("output", [])
                if outputs and isinstance(outputs, list):
                    first_out = outputs[0]
                    transcript = first_out.get("source", "") or first_out.get("target", "")
                elif isinstance(outputs, dict):
                    transcript = outputs.get("source", "")
                break

        if not transcript and pipeline_resp:
            first_task = pipeline_resp[0]
            outputs = first_task.get("output", [])
            if outputs:
                transcript = outputs[0].get("source", "")
    except Exception as e:
        logger.error(f"Failed to parse ASR response transcript: {e}")
        return {
            "success": False,
            "error": "Failed to extract recognized text from voice response.",
        }

    transcript = transcript.strip() if transcript else ""
    return {
        "success": True,
        "text": transcript,
        "language": language,
    }


async def synthesize_speech(
    text: str,
    language: str = "hi",
    gender: str = "female",
    speed: float = 1.0,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Step 2: TTS Pipeline Compute Call.
    Synthesizes Hindi text to spoken Base64 audio using Bhashini TTS.
    Returns safe browser-playable output format.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return {
            "success": False,
            "error": "Text payload is empty.",
        }

    if len(clean_text) > 1000:
        return {
            "success": False,
            "error": "Text length exceeds maximum allowed limit of 1000 characters.",
        }

    try:
        # Step 1: Config
        config = await fetch_pipeline_config("tts", language=language, client=client)
    except Exception as e:
        logger.error(f"Failed to fetch TTS config: {e}")
        return {
            "success": False,
            "error": "Text-to-speech service configuration unavailable.",
        }

    compute_payload = {
        "pipelineTasks": [
            {
                "taskType": "tts",
                "config": {
                    "language": {
                        "sourceLanguage": language
                    },
                    "serviceId": config["service_id"],
                    "gender": gender,
                    "speed": float(speed),
                    "samplingRate": 22050
                }
            }
        ],
        "inputData": {
            "input": [
                {
                    "source": clean_text
                }
            ],
            "audio": [
                {
                    "audioContent": None
                }
            ]
        }
    }

    inference_headers = {
        "Content-Type": "application/json",
        config["api_key_name"]: config["api_key_value"],
    }

    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=25.0)
        should_close_client = True

    try:
        response = await client.post(
            config["callback_url"],
            json=compute_payload,
            headers=inference_headers,
        )
        if response.status_code != 200:
            logger.error(f"Bhashini TTS compute failed with status {response.status_code}: {response.text}")
            return {
                "success": False,
                "error": "Speech generation failed. Please try again.",
            }

        result = response.json()
    except Exception as e:
        logger.error(f"Error during TTS compute call: {e}")
        return {
            "success": False,
            "error": "Voice synthesis request timed out or network error occurred.",
        }
    finally:
        if should_close_client:
            await client.aclose()

    # Extract synthesized audio
    audio_base64 = ""
    try:
        pipeline_resp = result.get("pipelineResponse", [])
        for task in pipeline_resp:
            if task.get("taskType") == "tts":
                audio_list = task.get("audio", [])
                if audio_list and isinstance(audio_list, list):
                    audio_base64 = audio_list[0].get("audioContent", "")
                elif isinstance(audio_list, dict):
                    audio_base64 = audio_list.get("audioContent", "")
                break

        if not audio_base64 and pipeline_resp:
            first_task = pipeline_resp[0]
            audio_list = first_task.get("audio", [])
            if audio_list:
                audio_base64 = audio_list[0].get("audioContent", "")
    except Exception as e:
        logger.error(f"Failed to parse TTS audio content: {e}")
        return {
            "success": False,
            "error": "Failed to extract synthesized audio from voice response.",
        }

    if not audio_base64:
        return {
            "success": False,
            "error": "No audio content returned by speech synthesis engine.",
        }

    # Clean whitespace/newlines from base64
    audio_base64 = audio_base64.strip().replace("\n", "").replace("\r", "")

    return {
        "success": True,
        "audio_base64": audio_base64,
        "audio_format": "wav",
        "mime_type": "audio/wav",
        "data_url": f"data:audio/wav;base64,{audio_base64}",
    }
