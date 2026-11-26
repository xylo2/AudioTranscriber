# -*- coding: utf-8 -*-
"""
Chargement et décodage de flux audio PCM (WAV, Audacity .aup3, PyAV).

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import sqlite3
from typing import Tuple
import wave
import numpy as np


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
            elif sampwidth == 4:
                arr = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                return np.zeros((0, channels), dtype=np.float32), rate
            usable: int = (arr.size // channels) * channels
            return arr[:usable].reshape(-1, channels), rate
        except Exception:
            return np.zeros((0, 1), dtype=np.float32), 16000
    @staticmethod
    def _load_aup3(file_path: str) -> Tuple[np.ndarray, int]:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(file_path)
            cur = conn.cursor()
            cur.execute("SELECT samples FROM sampleblocks ORDER BY blockid")
            rows = cur.fetchall()
            if not rows:
                return np.zeros((0, 1), dtype=np.float32), 44100
            raw_bytes: bytes = b"".join(
                next(iter(r)) for r in rows if r and next(iter(r))
            )
            arr = np.frombuffer(raw_bytes, dtype=np.float32)
            if arr.size == 0:
                return np.zeros((0, 1), dtype=np.float32), 44100
            return arr.reshape(-1, 1), 44100
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
                if nd.ndim == 2:
                    nd = nd.T
                else:
                    nd = nd.reshape(-1, 1)
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
