# -*- coding: utf-8 -*-
"""
Moteur principal de transcription audio et d'attribution des interlocuteurs.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import threading
from typing import Any, Callable, List, Optional
from audio_transcriber.config import TranscriberConfig
from audio_transcriber.diarizer import SpeakerDiarizer
from audio_transcriber.models import TranscriptSegment, TranscriptionResult


class AudioTranscriber:
    """Orchestre le chargement paresseux de Whisper, la transcription et la diarisation."""

    def __init__(
        self,
        config: Optional[TranscriberConfig] = None,
        model_override: Optional[Any] = None,
    ) -> None:
        self.config: TranscriberConfig = config or TranscriberConfig()
        self._model: Optional[Any] = model_override
        self._diarizer: SpeakerDiarizer = SpeakerDiarizer(
            max_speakers=self.config.max_speakers,
            similarity_threshold=self.config.similarity_threshold,
            speaker_prefix=self.config.speaker_prefix,
            profiles_path=self.config.profiles_path,
        )

    def _sync_diarizer_config(self) -> SpeakerDiarizer:
        """Synchronise le diarizer si la configuration a évolué."""
        self._diarizer.max_speakers = max(1, int(self.config.max_speakers))
        self._diarizer.similarity_threshold = float(self.config.similarity_threshold)
        self._diarizer.speaker_prefix = (
            self.config.speaker_prefix.strip() or "Interlocuteur"
        )
        new_path: str = self.config.profiles_path.strip()
        if new_path != self._diarizer.profiles_path:
            self._diarizer.profiles_path = new_path
            self._diarizer.clear_profiles()
            if new_path and os.path.isfile(new_path):
                self._diarizer.load_profiles(new_path)
        return self._diarizer

    @property
    def diarizer(self) -> SpeakerDiarizer:
        """Retourne l'instance de diarisation (gestion des profils vocaux)."""
        return self._sync_diarizer_config()
    @property
    def model(self) -> Any:
        """Charge le modèle faster-whisper à la demande (cache local prioritaire)."""
        if self._model is None:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]

            cache_dir: str = self.config.resolve_cache_dir()
            try:
                self._model = WhisperModel(
                    self.config.model_size,
                    device=self.config.device,
                    compute_type=self.config.compute_type,
                    download_root=cache_dir,
                    local_files_only=True,
                )
            except Exception:
                self._model = WhisperModel(
                    self.config.model_size,
                    device=self.config.device,
                    compute_type=self.config.compute_type,
                    download_root=cache_dir,
                    local_files_only=False,
                )
        return self._model

    def transcribe(
        self,
        file_path: str,
        stop_event: Optional[threading.Event] = None,
        on_segment: Optional[Callable[[TranscriptSegment], None]] = None,
    ) -> TranscriptionResult:
        """Transcrit un fichier audio/vidéo et attribue les interlocuteurs."""
        if not file_path or not os.path.isfile(file_path):
            raise FileNotFoundError(f"Fichier audio introuvable : '{file_path}'")

        raw_segments, info = self.model.transcribe(
            file_path,
            language=self.config.language,
            beam_size=self.config.beam_size,
            vad_filter=self.config.vad_filter,
        )

        segments: List[TranscriptSegment] = []
        for raw_seg in raw_segments:
            if stop_event is not None and stop_event.is_set():
                break
            clean_txt: str = str(getattr(raw_seg, "text", "") or "").strip()
            if not clean_txt:
                continue
            seg = TranscriptSegment(
                start=float(getattr(raw_seg, "start", 0.0) or 0.0),
                end=float(getattr(raw_seg, "end", 0.0) or 0.0),
                text=clean_txt,
            )
            segments.append(seg)
            if on_segment is not None:
                on_segment(seg)

        speakers: List[str] = []
        if segments and self.config.enable_diarization:
            speakers = self.diarizer.assign_speakers(file_path, segments)

        detected_lang: str = str(getattr(info, "language", "") or "")
        total_dur: float = float(
            getattr(info, "duration", 0.0)
            or (segments[-1].end if segments else 0.0)
        )
        return TranscriptionResult(
            source_path=os.path.abspath(file_path),
            language=detected_lang,
            duration=total_dur,
            speakers=speakers,
            segments=segments,
        )
