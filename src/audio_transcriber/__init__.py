# -*- coding: utf-8 -*-
"""
Paquet principal de transcription audio et diarisation multi-interlocuteurs.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

from audio_transcriber.audio_loader import (
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    is_supported_media,
)
from audio_transcriber.config import TranscriberConfig
from audio_transcriber.diarizer import SpeakerDiarizer
from audio_transcriber.engine import AudioTranscriber
from audio_transcriber.models import TranscriptSegment, TranscriptionResult

__all__ = [
    "AudioTranscriber",
    "SpeakerDiarizer",
    "SUPPORTED_AUDIO_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
    "SUPPORTED_VIDEO_EXTENSIONS",
    "TranscriberConfig",
    "TranscriptSegment",
    "TranscriptionResult",
    "is_supported_media",
]
