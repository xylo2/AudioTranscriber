# -*- coding: utf-8 -*-
"""
Configuration du moteur de transcription et de diarisation.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

from dataclasses import dataclass
import os


@dataclass
class TranscriberConfig:
    """Paramètres d'exécution de la transcription et de la diarisation."""

    model_size: str = "base"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str | None = None
    beam_size: int = 5
    vad_filter: bool = True
    enable_diarization: bool = True
    max_speakers: int = 6
    speaker_prefix: str = "Interlocuteur"
    similarity_threshold: float = 0.82
    cache_dir: str = ""
    profiles_path: str = ""

    def resolve_cache_dir(self) -> str:
        """Retourne et crée le répertoire de cache local des modèles Whisper."""
        raw_dir: str = self.cache_dir.strip() or os.path.join(
            os.path.expanduser("~"), ".cache", "audio_transcriber"
        )
        abs_dir: str = os.path.abspath(raw_dir)
        os.makedirs(abs_dir, exist_ok=True)
        return abs_dir
