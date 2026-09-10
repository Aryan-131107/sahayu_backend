# -*- coding: utf-8 -*-
"""
app/routers/voice.py - Bhashini AI Voice Assistant Router
Provides isolated FastAPI endpoints for Hindi ASR (Speech-to-Text)
and Hindi TTS (Text-to-Speech) for the Sahāyu Worker Dashboard.

Endpoints:
  POST /api/voice/transcribe  - Transcribe uploaded Hindi audio to text
  POST /api/voice/speak       - Synthesize Hindi text into spoken audio (Base64)
  GET  /api/voice/status      - Safe status of voice services (no credential leaks)
"""

import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel, Field

from app.services import bhashini_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice Assistant (Bhashini AI)"])


# ── Pydantic Request & Response Schemas ──────────────────────────────────────

class VoiceTranscribeResponse(BaseModel):
    success: bool
    text: Optional[str] = None
    language: Optional[str] = "hi"
    error: Optional[str] = None


class VoiceSpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Hindi text to synthesize")
    language: Optional[str] = Field("hi", description="Source language code (default: hi)")
    gender: Optional[str] = Field("female", description="Voice gender: 'female' or 'male'")
    speed: Optional[float] = Field(1.0, ge=0.5, le=2.0, description="Playback speed multiplier")


class VoiceSpeakResponse(BaseModel):
    success: bool
    audio_base64: Optional[str] = None
    audio_format: Optional[str] = "wav"
    mime_type: Optional[str] = "audio/wav"
    data_url: Optional[str] = None
    error: Optional[str] = None


class VoiceStatusResponse(BaseModel):
    success: bool
    is_configured: bool
    supported_language: str = "hi"
    pipeline_id: str
    cached_asr: bool
    cached_tts: bool


# ── Router Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/transcribe",
    response_model=VoiceTranscribeResponse,
    summary="Transcribe Hindi speech audio to text (Bhashini ASR)",
    description="Receives an audio recording from the frontend, calls Bhashini ASR, and returns recognized Hindi text.",
)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file recording from browser microphone"),
    language: str = Form("hi", description="Language code (default: hi)"),
):
    """
    Worker Dashboard Voice Input:
    1. Reads audio bytes from uploaded file.
    2. Determines audio format and sampling rate.
    3. Invokes Bhashini ASR pipeline (Step 1 Config -> Step 2 Compute).
    4. Returns recognized Hindi transcript.
    """
    if not file:
        return VoiceTranscribeResponse(
            success=False,
            error="No audio file provided in request.",
        )

    try:
        audio_bytes = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded audio file: {e}")
        return VoiceTranscribeResponse(
            success=False,
            error="Could not read uploaded audio file.",
        )

    if not audio_bytes or len(audio_bytes) < 100:
        return VoiceTranscribeResponse(
            success=False,
            error="Audio recording was too short or empty. Please speak again.",
        )

    content_type = file.content_type or ""
    result = await bhashini_service.transcribe_speech(
        audio_bytes=audio_bytes,
        content_type=content_type,
        language=language or "hi",
    )

    if not result.get("success"):
        return VoiceTranscribeResponse(
            success=False,
            error=result.get("error", "Voice recognition failed."),
        )

    return VoiceTranscribeResponse(
        success=True,
        text=result.get("text", ""),
        language=result.get("language", "hi"),
    )


@router.post(
    "/speak",
    response_model=VoiceSpeakResponse,
    summary="Synthesize Hindi text into spoken audio (Bhashini TTS)",
    description="Receives text in Hindi, calls Bhashini TTS, and returns Base64 audio for browser playback.",
)
async def speak_text(payload: VoiceSpeakRequest):
    """
    Worker Dashboard Voice Output:
    1. Validates text payload.
    2. Invokes Bhashini TTS pipeline (Step 1 Config -> Step 2 Compute).
    3. Returns browser-playable Base64 audio and data URL.
    """
    clean_text = (payload.text or "").strip()
    if not clean_text:
        return VoiceSpeakResponse(
            success=False,
            error="Text to speak cannot be empty.",
        )

    result = await bhashini_service.synthesize_speech(
        text=clean_text,
        language=payload.language or "hi",
        gender=payload.gender or "female",
        speed=payload.speed or 1.0,
    )

    if not result.get("success"):
        return VoiceSpeakResponse(
            success=False,
            error=result.get("error", "Text-to-speech synthesis failed."),
        )

    return VoiceSpeakResponse(
        success=True,
        audio_base64=result.get("audio_base64"),
        audio_format=result.get("audio_format", "wav"),
        mime_type=result.get("mime_type", "audio/wav"),
        data_url=result.get("data_url"),
    )


@router.get(
    "/status",
    response_model=VoiceStatusResponse,
    summary="Check Bhashini voice assistance status",
    description="Returns configuration status and cache availability without exposing credentials.",
)
def get_voice_status():
    """Returns safe diagnostic information about Bhashini voice module."""
    from app.core.config import settings

    cached_asr = bool(bhashini_service.get_cached_config("asr", "hi"))
    cached_tts = bool(bhashini_service.get_cached_config("tts", "hi"))

    return VoiceStatusResponse(
        success=True,
        is_configured=bhashini_service.is_configured(),
        supported_language="hi",
        pipeline_id=settings.BHASHINI_PIPELINE_ID,
        cached_asr=cached_asr,
        cached_tts=cached_tts,
    )

