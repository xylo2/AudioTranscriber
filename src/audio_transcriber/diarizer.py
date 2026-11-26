# -*- coding: utf-8 -*-
"""
Diarisation légère hors-ligne (stéréo + empreinte vocale spectrale NumPy).

Ce module attribue automatiquement un libellé de locuteur à chaque segment
transcrit sans dépendance neuronale lourde :
- en stéréo bi-canal faiblement corrélé : séparation par énergie gauche/droite ;
- en mono : extraction d'une empreinte spectrale multi-trames (16 bandes log
  + taux de passage par zéro) et regroupement par similarité cosinus ;
- persistance atomique des centroïdes vocaux au format JSON (`profiles_path`).

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Set
import numpy as np
from audio_transcriber.audio_loader import AudioSignalLoader
from audio_transcriber.models import TranscriptSegment


class SpeakerDiarizer:
    """Attribue et persiste les profils vocaux d'un fichier à l'autre."""

    def __init__(
        self,
        max_speakers: int = 6,
        similarity_threshold: float = 0.82,
        speaker_prefix: str = "Interlocuteur",
        profiles_path: str = "",
    ) -> None:
        """Initialise le diarizer et charge les profils JSON s'ils existent."""
        self.max_speakers: int = max(1, int(max_speakers))
        self.similarity_threshold: float = float(similarity_threshold)
        self.speaker_prefix: str = speaker_prefix.strip() or "Interlocuteur"
        self.profiles_path: str = profiles_path.strip()
        self._labels: List[str] = []
        self._centroids: List[np.ndarray] = []
        self._counts: List[int] = []
        if self.profiles_path and os.path.isfile(self.profiles_path):
            self.load_profiles(self.profiles_path)

    def clear_profiles(self) -> None:
        """Réinitialise tous les profils vocaux en mémoire."""
        self._labels.clear()
        self._centroids.clear()
        self._counts.clear()
    def rename_speaker(self, old_label: str, new_label: str) -> bool:
        """Renomme un profil vocal existant (ex. Interlocuteur_1 -> Alice)."""
        clean_new: str = new_label.strip()
        if not clean_new or old_label not in self._labels:
            return False
        if clean_new != old_label and clean_new in self._labels:
            return False
        idx: int = self._labels.index(old_label)
        self._labels[idx] = clean_new
        if self.profiles_path:
            self.save_profiles(self.profiles_path)
        return True

    def save_profiles(self, file_path: Optional[str] = None) -> str:
        """Sauvegarde atomiquement les empreintes vocales au format JSON local."""
        target: str = (file_path or self.profiles_path).strip()
        if not target:
            raise ValueError("Aucun chemin de sauvegarde des profils défini.")
        abs_target: str = os.path.abspath(target)
        parent: str = os.path.dirname(abs_target) or "."
        os.makedirs(parent, exist_ok=True)
        entries: List[Dict[str, Any]] = []
        for lbl, vec, cnt in zip(self._labels, self._centroids, self._counts):
            entries.append({
                "label": lbl,
                "count": int(cnt),
                "centroid": [round(float(x), 6) for x in vec.tolist()],
            })
        payload: Dict[str, Any] = {"version": 2, "profiles": entries}
        fd, tmp_path = tempfile.mkstemp(prefix=".voices_", suffix=".tmp", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, abs_target)
        except Exception:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
            raise
        return abs_target
    def load_profiles(self, file_path: Optional[str] = None) -> int:
        """Charge les empreintes vocales depuis un fichier JSON existant."""
        target: str = (file_path or self.profiles_path).strip()
        if not target or not os.path.isfile(target):
            return 0
        try:
            with open(target, "r", encoding="utf-8") as fh:
                data: Any = json.load(fh)
        except (OSError, ValueError):
            self.clear_profiles()
            return 0
        raw_list: Any = data.get("profiles", []) if isinstance(data, dict) else []
        self.clear_profiles()
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            lbl: str = str(item.get("label", "")).strip()
            raw_vec: Any = item.get("centroid", [])
            if not lbl or lbl in self._labels or not isinstance(raw_vec, list) or not raw_vec:
                continue
            try:
                vec = np.array([float(v) for v in raw_vec], dtype=np.float32)
            except (TypeError, ValueError):
                continue
            norm: float = float(np.linalg.norm(vec))
            if not np.isfinite(norm) or norm <= 1e-8:
                continue
            self._labels.append(lbl)
            self._centroids.append(vec / norm)
            self._counts.append(max(1, int(item.get("count", 1))))
        return len(self._labels)

    def assign_speakers(
        self,
        file_path: str,
        segments: List[TranscriptSegment],
    ) -> List[str]:
        """Renseigne seg.speaker en place et retourne la liste ordonnée des voix."""
        if not segments:
            return []
        if not self.profiles_path:
            self.clear_profiles()
        samples, sample_rate = AudioSignalLoader.load_audio(file_path)
        if samples.size == 0 or sample_rate <= 0:
            default_lbl: str = self._next_speaker_label()
            for seg in segments:
                seg.speaker = default_lbl
            return [default_lbl]

        _, n_channels = samples.shape
        if (
            self.max_speakers >= 2
            and n_channels >= 2
            and self._is_dual_channel_dialogue(samples)
        ):
            speakers = self._assign_by_stereo_channels(samples, sample_rate, segments)
        else:
            mono: np.ndarray = samples.mean(axis=1)
            speakers = self._assign_by_vocal_embedding(mono, sample_rate, segments)

        if self.profiles_path and self._labels:
            self.save_profiles(self.profiles_path)
        return speakers
    def _next_speaker_label(self, reserved: Optional[Set[str]] = None) -> str:
        """Génère le prochain libellé libre (ex. Interlocuteur_1)."""
        idx: int = len(self._labels) + 1
        blocked: Set[str] = set(self._labels) | (reserved or set())
        candidate: str = f"{self.speaker_prefix}_{idx}"
        while candidate in blocked:
            idx += 1
            candidate = f"{self.speaker_prefix}_{idx}"
        return candidate

    def _match_or_register_embedding(
        self,
        emb: np.ndarray,
        max_match_pool: Optional[int] = None,
        excluded_labels: Optional[Set[str]] = None,
    ) -> str:
        """Associe une empreinte à un centroïde proche ou crée un nouveau profil."""
        pool_limit: int = (
            len(self._centroids) if max_match_pool is None else max_match_pool
        )
        blocked: Set[str] = excluded_labels or set()
        best_idx: int = -1
        best_sim: float = -1.0
        for idx, center in enumerate(self._centroids[:pool_limit]):
            if self._labels[idx] in blocked or center.shape != emb.shape:
                continue
            sim: float = float(np.dot(emb, center))
            if sim > best_sim:
                best_sim = sim
                best_idx = idx

        if best_idx >= 0 and best_sim >= self.similarity_threshold:
            n: int = self._counts[best_idx]
            updated: np.ndarray = (self._centroids[best_idx] * n + emb) / float(n + 1)
            self._centroids[best_idx] = updated / (float(np.linalg.norm(updated)) or 1.0)
            self._counts[best_idx] = n + 1
            return self._labels[best_idx]

        if len(self._centroids) < self.max_speakers:
            lbl: str = self._next_speaker_label(reserved=blocked)
            self._labels.append(lbl)
            self._centroids.append(emb)
            self._counts.append(1)
            return lbl

        if best_idx >= 0:
            return self._labels[best_idx]
        for lbl in self._labels:
            if lbl not in blocked:
                return lbl
        return self._next_speaker_label(reserved=blocked)
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
        """Attribue les locuteurs selon le canal stéréo dominant (gauche/droite)."""
        seen: List[str] = []
        total_len, _ = samples.shape
        existing_count: int = len(self._centroids)
        seg_channels: List[int] = []
        channel_chunks: Dict[int, List[np.ndarray]] = {0: [], 1: []}
        for seg in segments:
            i0: int = max(0, min(total_len, int(seg.start * sample_rate)))
            i1: int = max(i0 + 1, min(total_len, int(seg.end * sample_rate)))
            chunk: np.ndarray = samples[i0:i1]
            e_left: float = float(np.mean(chunk[:, 0] ** 2)) if chunk.size else 0.0
            e_right: float = float(np.mean(chunk[:, 1] ** 2)) if chunk.size else 0.0
            ch_idx: int = 0 if e_left >= e_right else 1
            seg_channels.append(ch_idx)
            channel_chunks[ch_idx].append(chunk[:, ch_idx])

        channel_labels: Dict[int, str] = {}
        for ch_idx in (0, 1):
            if not channel_chunks[ch_idx]:
                continue
            other_labels: Set[str] = set(channel_labels.values())
            merged: np.ndarray = np.concatenate(channel_chunks[ch_idx])
            emb = self._extract_voice_signature(merged, sample_rate)
            if emb is not None:
                channel_labels[ch_idx] = self._match_or_register_embedding(
                    emb, max_match_pool=existing_count, excluded_labels=other_labels
                )
            else:
                channel_labels[ch_idx] = self._next_speaker_label(reserved=other_labels)

        for seg, ch_idx in zip(segments, seg_channels):
            lbl: str = channel_labels[ch_idx]
            seg.speaker = lbl
            if lbl not in seen:
                seen.append(lbl)
        return seen

    @staticmethod
    def _extract_voice_signature(
        chunk: np.ndarray, sample_rate: int
    ) -> np.ndarray | None:
        """Calcule une empreinte spectrale multi-trames (bandes log + centroïde + ZCR)."""
        min_samples: int = max(256, sample_rate // 10)
        if chunk.size < min_samples:
            return None
        global_rms: float = float(np.sqrt(np.mean(chunk ** 2)))
        if global_rms < 1e-4:
            return None
        frame_len: int = min(2048, chunk.size)
        win: np.ndarray = np.hanning(frame_len)
        max_start: int = max(0, chunk.size - frame_len)
        n_frames: int = min(8, max(1, chunk.size // frame_len))
        starts = np.linspace(0, max_start, num=n_frames, dtype=int)
        spectra: List[np.ndarray] = []
        zcrs: List[float] = []
        for st in starts:
            frame: np.ndarray = chunk[st : st + frame_len]
            f_rms: float = float(np.sqrt(np.mean(frame ** 2)))
            if f_rms < global_rms * 0.25:
                continue
            norm_f: np.ndarray = frame / f_rms
            spec: np.ndarray = np.abs(np.fft.rfft(norm_f * win)) + 1e-8
            spectra.append(np.log(spec))
            zcrs.append(float(np.mean(np.abs(np.diff(np.signbit(norm_f))))))
        if not spectra:
            return None
        mean_log_spec: np.ndarray = np.mean(np.vstack(spectra), axis=0)
        bins: np.ndarray = np.array_split(
            mean_log_spec[: min(256, mean_log_spec.size)], 16
        )
        band_means: np.ndarray = np.array(
            [float(np.mean(b)) for b in bins], dtype=np.float32
        )
        mean_zcr: float = float(np.mean(zcrs))
        feat: np.ndarray = np.append(band_means, np.float32(mean_zcr * 10.0))
        norm: float = float(np.linalg.norm(feat))
        return (feat / norm) if norm > 1e-8 else None

    def _assign_by_vocal_embedding(
        self,
        mono: np.ndarray,
        sample_rate: int,
        segments: List[TranscriptSegment],
    ) -> List[str]:
        """Attribue les locuteurs en mono par comparaison des empreintes spectrales."""
        speakers_order: List[str] = []
        total_len: int = mono.size
        for seg in segments:
            i0: int = max(0, min(total_len, int(seg.start * sample_rate)))
            i1: int = max(i0 + 1, min(total_len, int(seg.end * sample_rate)))
            emb = self._extract_voice_signature(mono[i0:i1], sample_rate)
            if emb is None:
                lbl: str = speakers_order[-1] if speakers_order else self._next_speaker_label()
            else:
                lbl = self._match_or_register_embedding(emb)
            seg.speaker = lbl
            if lbl not in speakers_order:
                speakers_order.append(lbl)
        return speakers_order
