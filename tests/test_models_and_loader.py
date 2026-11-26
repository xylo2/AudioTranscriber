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
import unittest
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
    """Vérifie le formatage texte/LRC et le décodage WAV / Audacity .aup3."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_models_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_result_formatting_timestamped_and_lrc(self) -> None:
        seg1 = TranscriptSegment(start=5.2, end=9.0, text="Bonjour.", speaker="Interlocuteur_1")
        seg2 = TranscriptSegment(start=65.5, end=70.0, text="Merci.", speaker="Interlocuteur_2")
        res = TranscriptionResult(
            source_path="/tmp/test.wav",
            language="fr",
            duration=70.0,
            speakers=["Interlocuteur_1", "Interlocuteur_2"],
            segments=[seg1, seg2],
        )
        self.assertEqual(res.to_plain_text(), "Bonjour.\nMerci.")
        self.assertIn("[00:05] Interlocuteur_1 : Bonjour.", res.to_timestamped_text())
        self.assertIn("[01:05.50] Interlocuteur_2 : Merci.", res.to_lrc_text())
        self.assertEqual(len(res.to_dict().get("segments", [])), 2)

    def test_load_wav_and_aup3_files(self) -> None:
        wav_path: str = os.path.join(self.tmp_dir, "sample.wav")
        t = np.linspace(0.0, 0.5, 8000, endpoint=False)
        pcm = (np.sin(2.0 * np.pi * 440.0 * t) * 16000.0).astype(np.int16)
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm.tobytes())

        samples, rate = AudioSignalLoader.load_audio(wav_path)
        self.assertEqual(rate, 16000)
        self.assertEqual(samples.shape, (8000, 1))

        aup3_path: str = os.path.join(self.tmp_dir, "projet.aup3")
        conn = sqlite3.connect(aup3_path)
        conn.execute("CREATE TABLE sampleblocks (blockid INTEGER PRIMARY KEY, samples BLOB)")
        arr_f32 = np.ones(400, dtype=np.float32) * 0.25
        conn.execute("INSERT INTO sampleblocks (blockid, samples) VALUES (1, ?)", (arr_f32.tobytes(),))
        conn.commit()
        conn.close()

        aup_samples, aup_rate = AudioSignalLoader.load_audio(aup3_path)
        self.assertEqual(aup_rate, 44100)
        self.assertEqual(aup_samples.shape, (400, 1))


if __name__ == "__main__":
    unittest.main()
