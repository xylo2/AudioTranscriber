# -*- coding: utf-8 -*-
"""
Chargement et décodage de flux audio PCM (WAV, Audacity .aup3, PyAV).

Ce module unifie la lecture de tous les médias supportés sous forme de
matrices NumPy ``float32`` 2D ``(échantillons, canaux)`` normalisées dans
``[-1.0, 1.0]``, accompagnées de leur fréquence d'échantillonnage.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import re
import sqlite3
from typing import FrozenSet, Tuple
import wave
import numpy as np

SUPPORTED_AUDIO_EXTENSIONS: FrozenSet[str] = frozenset({
    ".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma", ".aup3",
})

SUPPORTED_VIDEO_EXTENSIONS: FrozenSet[str] = frozenset({
    ".mp4", ".mov", ".mts", ".m2ts", ".3gp", ".mpg", ".mpeg", ".wmv", ".mkv", ".avi", ".webm",
})

SUPPORTED_EXTENSIONS: FrozenSet[str] = (
    SUPPORTED_AUDIO_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS
)


def is_supported_media(file_path: str) -> bool:
    """Retourne True si l'extension du fichier est prise en charge par la librairie."""
    if not file_path:
        return False
    ext: str = os.path.splitext(file_path)[-1].lower()
    return ext in SUPPORTED_EXTENSIONS


class AudioSignalLoader:
    """Charge un fichier audio sous forme de matrice NumPy float32 (N, canaux)."""

    @staticmethod
    def load_audio(file_path: str) -> Tuple[np.ndarray, int]:
        """Retourne (samples_float32_2d, sample_rate) ou tableau vide si illisible."""
        if not file_path or not os.path.isfile(file_path):
            return np.zeros((0, 1), dtype=np.float32), 16000
        ext: str = os.path.splitext(file_path)[-1].lower()
        if ext == ".wav":
            return AudioSignalLoader._load_wav(file_path)
        if ext == ".aup3":
            return AudioSignalLoader._load_aup3(file_path)
        return AudioSignalLoader._load_via_av(file_path)
    @staticmethod
    def _load_wav(file_path: str) -> Tuple[np.ndarray, int]:
        """Décode un fichier WAV PCM 8, 16, 24 ou 32 bits en matrice float32."""
        try:
            with wave.open(file_path, "rb") as wf:
                channels: int = max(1, wf.getnchannels())
                sampwidth: int = wf.getsampwidth()
                rate: int = wf.getframerate()
                frames: bytes = wf.readframes(wf.getnframes())
            if not frames:
                return np.zeros((0, channels), dtype=np.float32), rate
            if sampwidth == 1:
                arr = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            elif sampwidth == 2:
                arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            elif sampwidth == 3:
                raw_u8 = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
                sign = np.where(raw_u8[:, 2] & 0x80, 0xFF, 0x00).astype(np.uint8)
                padded = np.column_stack([raw_u8, sign]).ravel()
                arr = np.frombuffer(padded.tobytes(), dtype="<i4").astype(np.float32) / 8388608.0
            elif sampwidth == 4:
                arr = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                return np.zeros((0, channels), dtype=np.float32), rate
            usable: int = (arr.size // channels) * channels
            return arr[:usable].reshape(-1, channels), rate
        except Exception:
            return np.zeros((0, 1), dtype=np.float32), 16000

    @staticmethod
    def _extract_aup3_sample_rate(cur: sqlite3.Cursor) -> int:
        """Extrait le taux d'échantillonnage XML de la table project Audacity."""
        try:
            cur.execute("SELECT dict FROM project LIMIT 1")
            row = cur.fetchone()
            first_col = next(iter(row), None) if row else None
            if first_col:
                blob_txt: str = (
                    first_col.decode("utf-8", errors="ignore")
                    if isinstance(first_col, (bytes, bytearray))
                    else str(first_col)
                )
                match = re.search(r'rate=["\']([0-9]+(?:\.[0-9]+)?)["\']', blob_txt)
                if match:
                    parsed: int = int(float(match.group(1)))
                    if parsed > 0:
                        return parsed
        except sqlite3.Error:
            pass
        return 44100
    @staticmethod
    def _load_aup3(file_path: str) -> Tuple[np.ndarray, int]:
        """Concatène les blocs PCM float32 d'un projet SQLite Audacity .aup3."""
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(file_path)
            cur = conn.cursor()
            rate: int = AudioSignalLoader._extract_aup3_sample_rate(cur)
            cur.execute("SELECT samples FROM sampleblocks ORDER BY blockid")
            rows = cur.fetchall()
            if not rows:
                return np.zeros((0, 1), dtype=np.float32), rate
            raw_bytes: bytes = b"".join(
                next(iter(r)) for r in rows if r and next(iter(r))
            )
            arr = np.frombuffer(raw_bytes, dtype=np.float32)
            if arr.size == 0:
                return np.zeros((0, 1), dtype=np.float32), rate
            return arr.reshape(-1, 1), rate
        except Exception:
            return np.zeros((0, 1), dtype=np.float32), 44100
        finally:
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass

    @staticmethod
    def _load_via_av(file_path: str) -> Tuple[np.ndarray, int]:
        """Décode la piste audio de tout conteneur média pris en charge par PyAV."""
        try:
            import av  # type: ignore[import-not-found]
        except ImportError:
            return np.zeros((0, 1), dtype=np.float32), 16000
        container = None
        try:
            container = av.open(file_path)
            if not container.streams.audio:
                return np.zeros((0, 1), dtype=np.float32), 16000
            stream = next(iter(container.streams.audio))
            rate: int = int(stream.rate or 16000)
            chunks: list[np.ndarray] = []
            for frame in container.decode(audio=0):
                nd: np.ndarray = frame.to_ndarray()
                nd = nd.T if nd.ndim == 2 else nd.reshape(-1, 1)
                if np.issubdtype(nd.dtype, np.integer):
                    max_v: float = float(np.iinfo(nd.dtype).max) or 1.0
                    nd_f = nd.astype(np.float32) / max_v
                else:
                    nd_f = nd.astype(np.float32)
                chunks.append(nd_f)
            if not chunks:
                return np.zeros((0, 1), dtype=np.float32), rate
            return np.vstack(chunks), rate
        except Exception:
            return np.zeros((0, 1), dtype=np.float32), 16000
        finally:
            if container is not None:
                try:
                    container.close()
                except Exception:
                    pass
