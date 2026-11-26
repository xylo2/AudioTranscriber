# -*- coding: utf-8 -*-
"""
Tests unitaires des modèles (MM:SS, LRC, JSON) et du chargeur audio.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

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

from audio_transcriber.audio_loader import AudioSignalLoader
from audio_transcriber.models import TranscriptSegment, TranscriptionResult


class TestModelsAndLoader(unittest.TestCase):
    """Vérifie le formatage texte/LRC et le décodage WAV / Audacity .aup3 / PyAV."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_models_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_result_formatting_timestamped_and_lrc(self) -> None:
        seg1 = TranscriptSegment(start=5.2, end=9.0, text="Bonjour.", speaker="Interlocuteur_1")
        seg_empty = TranscriptSegment(start=10.0, end=11.0, text="   ", speaker="Interlocuteur_1")
        seg2 = TranscriptSegment(start=65.5, end=70.0, text="Merci.", speaker="Interlocuteur_2")
        res = TranscriptionResult(
            source_path="/tmp/test.wav",
            language="fr",
            duration=70.0,
            speakers=["Interlocuteur_1", "Interlocuteur_2"],
            segments=[seg1, seg_empty, seg2],
        )
        self.assertEqual(res.to_plain_text(), "Bonjour.\nMerci.")
        self.assertIn("[00:05] Interlocuteur_1 : Bonjour.", res.to_timestamped_text())
        self.assertEqual(
            res.to_timestamped_text(include_speaker=False),
            "[00:05] Bonjour.\n[01:05] Merci.",
        )
        self.assertIn("[01:05.50] Interlocuteur_2 : Merci.", res.to_lrc_text())
        self.assertEqual(
            res.to_lrc_text(include_speaker=False),
            "[00:05.20] Bonjour.\n[01:05.50] Merci.",
        )
        self.assertEqual(len(res.to_dict().get("segments", [])), 3)
    def test_load_wav_variants_and_aup3_edge_cases(self) -> None:
        wav8: str = os.path.join(self.tmp_dir, "pcm8.wav")
        with wave.open(wav8, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(1)
            wf.setframerate(8000)
            wf.writeframes(bytes([128, 255]))
        s8, r8 = AudioSignalLoader.load_audio(wav8)
        self.assertEqual((r8, s8.shape), (8000, (2, 1)))

        wav32: str = os.path.join(self.tmp_dir, "pcm32_empty.wav")
        with wave.open(wav32, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(4)
            wf.setframerate(16000)
            wf.writeframes(b"")
        s32, _ = AudioSignalLoader.load_audio(wav32)
        self.assertEqual(s32.size, 0)

        bad_wav: str = os.path.join(self.tmp_dir, "corrupt.wav")
        with open(bad_wav, "wb") as fh:
            fh.write(b"NOT_A_RIFF_WAV")
        self.assertEqual(AudioSignalLoader.load_audio(bad_wav)[0].size, 0)

        aup3_empty: str = os.path.join(self.tmp_dir, "empty.aup3")
        conn = sqlite3.connect(aup3_empty)
        conn.execute("CREATE TABLE sampleblocks (blockid INTEGER PRIMARY KEY, samples BLOB)")
        conn.commit()
        conn.close()
        self.assertEqual(AudioSignalLoader.load_audio(aup3_empty)[0].size, 0)

    def test_load_via_av_mocked_and_fallback(self) -> None:
        mp3_path: str = os.path.join(self.tmp_dir, "clip.mp3")
        with open(mp3_path, "wb") as fh:
            fh.write(b"ID3")

        class _FakeFrame:
            def __init__(self, arr: np.ndarray) -> None:
                self._arr = arr

            def to_ndarray(self) -> np.ndarray:
                return self._arr

        class _FakeContainer:
            def __init__(self) -> None:
                self.streams = SimpleNamespace(audio=[SimpleNamespace(rate=24000)])

            def decode(self, audio: int = 0):
                yield _FakeFrame(np.array([[16384, -16384], [8192, -8192]], dtype=np.int16))
                yield _FakeFrame(np.array([[0.25, -0.25], [0.5, -0.5]], dtype=np.float32))

            def close(self) -> None:
                pass

        fake_av = SimpleNamespace(open=lambda _p: _FakeContainer())
        with patch.dict(sys.modules, {"av": fake_av}):
            samples, rate = AudioSignalLoader.load_audio(mp3_path)
        self.assertEqual(rate, 24000)
        self.assertEqual(samples.shape, (4, 2))


if __name__ == "__main__":
    unittest.main()
