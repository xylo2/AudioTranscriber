# -*- coding: utf-8 -*-
"""
Diarisation légère hors-ligne (stéréo + empreinte vocale spectrale NumPy).

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

from typing import List
import numpy as np
from audio_transcriber.audio_loader import AudioSignalLoader
from audio_transcriber.models import TranscriptSegment


class SpeakerDiarizer:
    """Attribue un identifiant d'interlocuteur à chaque segment de parole."""

    def __init__(
        self,
        max_speakers: int = 6,
        similarity_threshold: float = 0.82,
        speaker_prefix: str = "Interlocuteur",
    ) -> None:
        self.max_speakers: int = max(1, int(max_speakers))
        self.similarity_threshold: float = float(similarity_threshold)
        self.speaker_prefix: str = speaker_prefix.strip() or "Interlocuteur"

    def assign_speakers(
        self,
        file_path: str,
        segments: List[TranscriptSegment],
    ) -> List[str]:
        """Renseigne seg.speaker en place et retourne la liste ordonnée des voix."""
        if not segments:
            return []
        samples, sample_rate = AudioSignalLoader.load_audio(file_path)
        if samples.size == 0 or sample_rate <= 0:
            default_lbl: str = f"{self.speaker_prefix}_1"
            for seg in segments:
                seg.speaker = default_lbl
            return [default_lbl]

        _, n_channels = samples.shape
        if n_channels >= 2 and self._is_dual_channel_dialogue(samples):
            return self._assign_by_stereo_channels(samples, sample_rate, segments)

        mono: np.ndarray = samples.mean(axis=1)
        return self._assign_by_vocal_embedding(mono, sample_rate, segments)

    @staticmethod
    def _is_dual_channel_dialogue(samples: np.ndarray) -> bool:
        """Détecte si deux canaux distincts portent des interlocuteurs séparés."""
        left: np.ndarray = samples[:, 0]
        right: np.ndarray = samples[:, 1]
        norm_l: float = float(np.linalg.norm(left))
        norm_r: float = float(np.linalg.norm(right))
        if norm_l < 1e-5 or norm_r < 1e-5:
            return False
        corr: float = abs(float(np.dot(left, right)) / (norm_l * norm_r))
        return corr < 0.45
    def _assign_by_stereo_channels(
        self,
        samples: np.ndarray,
        sample_rate: int,
        segments: List[TranscriptSegment],
    ) -> List[str]:
        seen: List[str] = []
        total_len, _ = samples.shape
        for seg in segments:
            i0: int = max(0, min(total_len, int(seg.start * sample_rate)))
            i1: int = max(i0 + 1, min(total_len, int(seg.end * sample_rate)))
            chunk: np.ndarray = samples[i0:i1]
            e_left: float = float(np.mean(chunk[:, 0] ** 2)) if chunk.size else 0.0
            e_right: float = float(np.mean(chunk[:, 1] ** 2)) if chunk.size else 0.0
            ch_idx: int = 1 if e_left >= e_right else 2
            lbl: str = f"{self.speaker_prefix}_{ch_idx}"
            seg.speaker = lbl
            if lbl not in seen:
                seen.append(lbl)
        return seen

    @staticmethod
    def _extract_voice_signature(
        chunk: np.ndarray, sample_rate: int
    ) -> np.ndarray | None:
        """Calcule un vecteur d'empreinte spectrale normalisé (pitch + bandes)."""
        if chunk.size < max(256, sample_rate // 10):
            return None
        rms: float = float(np.sqrt(np.mean(chunk ** 2)))
        if rms < 1e-4:
            return None
        sig: np.ndarray = chunk / rms
        frame_len: int = min(2048, sig.size)
        win: np.ndarray = np.hanning(frame_len)
        spec: np.ndarray = np.abs(np.fft.rfft(sig[:frame_len] * win)) + 1e-8
        log_spec: np.ndarray = np.log(spec)
        bins: np.ndarray = np.array_split(log_spec[: min(256, log_spec.size)], 16)
        band_means: np.ndarray = np.array([float(np.mean(b)) for b in bins], dtype=np.float32)
        zcr: float = float(np.mean(np.abs(np.diff(np.signbit(sig)))))
        feat: np.ndarray = np.append(band_means, np.float32(zcr * 10.0))
        norm: float = float(np.linalg.norm(feat))
        return (feat / norm) if norm > 1e-8 else None

    def _assign_by_vocal_embedding(
        self,
        mono: np.ndarray,
        sample_rate: int,
        segments: List[TranscriptSegment],
    ) -> List[str]:
        centroids: List[np.ndarray] = []
        counts: List[int] = []
        speakers_order: List[str] = []
        total_len: int = mono.size

        for seg in segments:
            i0: int = max(0, min(total_len, int(seg.start * sample_rate)))
            i1: int = max(i0 + 1, min(total_len, int(seg.end * sample_rate)))
            emb = self._extract_voice_signature(mono[i0:i1], sample_rate)
            if emb is None:
                lbl: str = speakers_order[-1] if speakers_order else f"{self.speaker_prefix}_1"
                seg.speaker = lbl
                if lbl not in speakers_order:
                    speakers_order.append(lbl)
                continue

            best_idx: int = -1
            best_sim: float = -1.0
            for idx, center in enumerate(centroids):
                sim: float = float(np.dot(emb, center))
                if sim > best_sim:
                    best_sim = sim
                    best_idx = idx

            if best_idx >= 0 and best_sim >= self.similarity_threshold:
                n: int = counts[best_idx]
                updated: np.ndarray = (centroids[best_idx] * n + emb) / float(n + 1)
                centroids[best_idx] = updated / (float(np.linalg.norm(updated)) or 1.0)
                counts[best_idx] = n + 1
                chosen_idx: int = best_idx
            elif len(centroids) < self.max_speakers:
                centroids.append(emb)
                counts.append(1)
                chosen_idx = len(centroids) - 1
            else:
                chosen_idx = max(0, best_idx)

            lbl = f"{self.speaker_prefix}_{chosen_idx + 1}"
            seg.speaker = lbl
            if lbl not in speakers_order:
                speakers_order.append(lbl)
        return speakers_order
