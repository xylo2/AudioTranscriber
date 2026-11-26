# -*- coding: utf-8 -*-
"""
Tests de résilience I/O (WAV, .aup3, PyAV) et de diarisation stéréo/profils.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave
import numpy as np

SRC_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from audio_transcriber import SpeakerDiarizer, TranscriptSegment
from audio_transcriber.audio_loader import AudioSignalLoader


class TestFinalCoverage(unittest.TestCase):
    """Vérifie la résilience aux fichiers défectueux et aux cas limites stéréo."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_final_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_loader_wav32_invalid_width_aup3_and_av_branches(self) -> None:
        wav32: str = os.path.join(self.tmp_dir, "pcm32_full.wav")
        with wave.open(wav32, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(4)
            wf.setframerate(16000)
            wf.writeframes(np.array([1073741824, -1073741824], dtype=np.int32).tobytes())
        s32, r32 = AudioSignalLoader.load_audio(wav32)
        self.assertEqual((r32, s32.shape), (16000, (2, 1)))

        class _FakeBadWidthWav:
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def getnchannels(self) -> int:
                return 1

            def getsampwidth(self) -> int:
                return 8

            def getframerate(self) -> int:
                return 16000

            def getnframes(self) -> int:
                return 2

            def readframes(self, _n: int) -> bytes:
                return b"\x00" * 16

        with patch("wave.open", return_value=_FakeBadWidthWav()):
            s_bad, _ = AudioSignalLoader.load_audio(wav32)
            self.assertEqual(s_bad.size, 0)

        aup3_zero: str = os.path.join(self.tmp_dir, "zero_bytes.aup3")
        conn = sqlite3.connect(aup3_zero)
        conn.execute("CREATE TABLE sampleblocks (blockid INTEGER PRIMARY KEY, samples BLOB)")
        conn.execute("INSERT INTO sampleblocks (blockid, samples) VALUES (1, ?)", (b"",))
        conn.commit()
        conn.close()
        s_aup_z, _ = AudioSignalLoader.load_audio(aup3_zero)
        self.assertEqual(s_aup_z.size, 0)

        class _BrokenCloseConn:
            def cursor(self):
                raise RuntimeError("Curseur HS")

            def close(self) -> None:
                raise sqlite3.Error("Fermeture HS")

        with patch("sqlite3.connect", return_value=_BrokenCloseConn()):
            s_aup_err, _ = AudioSignalLoader.load_audio(aup3_zero)
            self.assertEqual(s_aup_err.size, 0)
    def test_loader_av_no_stream_empty_and_missing(self) -> None:
        ogg_path: str = os.path.join(self.tmp_dir, "test.ogg")
        with open(ogg_path, "wb") as fh:
            fh.write(b"OggS")

        with patch.dict(sys.modules, {"av": None}):
            s_missing, _ = AudioSignalLoader.load_audio(ogg_path)
            self.assertEqual(s_missing.size, 0)

        class _NoAudioContainer:
            streams = SimpleNamespace(audio=[])

            def close(self) -> None:
                pass

        class _EmptyDecodeContainer:
            streams = SimpleNamespace(audio=[SimpleNamespace(rate=48000)])

            def decode(self, audio: int = 0):
                return iter(())

            def close(self) -> None:
                pass

        class _BrokenDecodeContainer:
            streams = SimpleNamespace(audio=[SimpleNamespace(rate=48000)])

            def decode(self, audio: int = 0):
                raise RuntimeError("Flux corrompu")

            def close(self) -> None:
                raise RuntimeError("Fermeture av impossible")

        for ctr in (_NoAudioContainer(), _EmptyDecodeContainer(), _BrokenDecodeContainer()):
            fake_av = SimpleNamespace(open=lambda _p, c=ctr: c)
            with patch.dict(sys.modules, {"av": fake_av}):
                arr, _ = AudioSignalLoader.load_audio(ogg_path)
                self.assertEqual(arr.shape, (0, 1))

    def test_diarizer_realistic_saturation_and_stereo_single_active_channel(self) -> None:
        prof_path: str = os.path.join(self.tmp_dir, "profiles.json")
        with open(prof_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "profiles": [
                        "invalid_entry",
                        {"label": "", "centroid": [1.0] * 17},
                        {"label": "BadVec", "centroid": ["nan_text"]},
                        {"label": "ZeroVec", "centroid": [0.0] * 17},
                        {"label": "LegacyDim", "centroid": [1.0, 0.0], "count": 1},
                        {"label": "Interlocuteur_1", "centroid": [1.0] + [0.0] * 16, "count": 2},
                    ]
                },
                fh,
            )
        diarizer = SpeakerDiarizer(max_speakers=3, profiles_path=prof_path)
        self.assertEqual(diarizer.load_profiles(), 2)
        self.assertFalse(diarizer.rename_speaker("LegacyDim", "Interlocuteur_1"))

        # Vérifie le nettoyage du fichier temporaire en cas d'erreur os.replace
        with patch("os.replace", side_effect=OSError("Disque verrouillé")):
            with self.assertRaises(OSError):
                diarizer.save_profiles()

        # Stéréo dual-canal dont seul le canal gauche porte le segment transcrit
        sr: int = 16000
        t = np.linspace(0.0, 0.5, sr // 2, endpoint=False)
        left = np.concatenate([np.zeros(sr // 2), np.sin(2 * np.pi * 240 * t) * 0.7, np.zeros(sr // 2)])
        right = np.concatenate([np.zeros(sr), np.sin(2 * np.pi * 680 * t) * 0.7])
        stereo_one: str = os.path.join(self.tmp_dir, "stereo_one_side.wav")
        with wave.open(stereo_one, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            pcm = (np.column_stack([left, right]) * 16000).astype(np.int16)
            wf.writeframes(pcm.tobytes())

        segs = [TranscriptSegment(start=0.0, end=1.0, text="Voix gauche uniquement")]
        self.assertEqual(diarizer.assign_speakers(stereo_one, segs), ["Interlocuteur_3"])

        # Saturation (max_speakers=3 déjà atteint) : une nouvelle voix est rattachée sans créer _4
        mono_sat: str = os.path.join(self.tmp_dir, "mono_sat.wav")
        v3 = np.sin(2 * np.pi * 1500 * t) * 0.6
        with wave.open(mono_sat, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes((v3 * 16000).astype(np.int16).tobytes())
        sat_speakers = diarizer.assign_speakers(
            mono_sat, [TranscriptSegment(start=0.0, end=0.5, text="Troisième voix")]
        )
        self.assertEqual(len(sat_speakers), 1)


if __name__ == "__main__":
    unittest.main()
