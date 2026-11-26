# -*- coding: utf-8 -*-
"""
Paquet principal de transcription audio et diarisation multi-interlocuteurs.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

from importlib.metadata import PackageNotFoundError, version
import os
import re
from audio_transcriber.audio_extractor import (
    CODEC_TO_EXTENSION,
    VIDEO_EXT_TO_AUDIO_EXT,
    extract_audio,
    infer_audio_extension,
)
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


def _resolve_version() -> str:
    pyproject_path: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "pyproject.toml")
    )
    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, "r", encoding="utf-8") as fh:
                match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', fh.read())
                if match:
                    return match.group(1)
        except OSError:
            pass
    try:
        return version("audio-transcriber")
    except PackageNotFoundError:
        return "0.2.0"


__version__: str = _resolve_version()

__all__ = [
    "AudioTranscriber",
    "CODEC_TO_EXTENSION",
    "SpeakerDiarizer",
    "SUPPORTED_AUDIO_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
    "SUPPORTED_VIDEO_EXTENSIONS",
    "TranscriberConfig",
    "TranscriptSegment",
    "TranscriptionResult",
    "VIDEO_EXT_TO_AUDIO_EXT",
    "__version__",
    "extract_audio",
    "infer_audio_extension",
    "is_supported_media",
]
