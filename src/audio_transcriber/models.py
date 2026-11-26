# -*- coding: utf-8 -*-
"""
Modèles de données des segments transcrits et formats d'export.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranscriptSegment:
    """Représente un segment de parole horodaté avec son locuteur éventuel."""

    start: float
    end: float
    text: str
    speaker: str = ""

    def format_mmss(self) -> str:
        """Formate l'instant de début en [MM:SS]."""
        total_sec: int = max(0, int(self.start))
        mins, secs = divmod(total_sec, 60)
        return f"[{mins:02d}:{secs:02d}]"

    def format_lrc_timestamp(self) -> str:
        """Formate l'instant de début au format LRC [MM:SS.cc]."""
        clamped: float = max(0.0, float(self.start))
        total_cs: int = int(round(clamped * 100.0))
        mins, rem_cs = divmod(total_cs, 6000)
        secs, centis = divmod(rem_cs, 100)
        return f"[{mins:02d}:{secs:02d}.{centis:02d}]"

    def to_dict(self) -> dict[str, Any]:
        """Sérialise le segment en dictionnaire JSON-compatible."""
        return {
            "start": round(float(self.start), 3),
            "end": round(float(self.end), 3),
            "speaker": self.speaker,
            "text": self.text,
        }
@dataclass
class TranscriptionResult:
    """Résultat complet d'une transcription audio multi-interlocuteurs."""

    source_path: str
    language: str = ""
    duration: float = 0.0
    speakers: list[str] = field(default_factory=list)
    segments: list[TranscriptSegment] = field(default_factory=list)

    def to_plain_text(self) -> str:
        """Retourne le texte brut sans horodatage."""
        return "\n".join(
            seg.text.strip() for seg in self.segments if seg.text.strip()
        )

    def to_timestamped_text(self, include_speaker: bool = True) -> str:
        """Formate les segments en '[MM:SS] Interlocuteur_1 : Texte'."""
        lines: list[str] = []
        for seg in self.segments:
            clean_txt: str = seg.text.strip()
            if not clean_txt:
                continue
            ts: str = seg.format_mmss()
            if include_speaker and seg.speaker:
                lines.append(f"{ts} {seg.speaker} : {clean_txt}")
            else:
                lines.append(f"{ts} {clean_txt}")
        return "\n".join(lines)

    def to_lrc_text(self, include_speaker: bool = True) -> str:
        """Formate les segments au format karaoké synchronisé LRC."""
        lines: list[str] = []
        for seg in self.segments:
            clean_txt: str = seg.text.strip()
            if not clean_txt:
                continue
            ts_lrc: str = seg.format_lrc_timestamp()
            if include_speaker and seg.speaker:
                lines.append(f"{ts_lrc} {seg.speaker} : {clean_txt}")
            else:
                lines.append(f"{ts_lrc} {clean_txt}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Sérialise l'intégralité du résultat en dictionnaire."""
        return {
            "source_path": self.source_path,
            "language": self.language,
            "duration": round(float(self.duration), 3),
            "speakers": list(self.speakers),
            "segments": [seg.to_dict() for seg in self.segments],
        }
