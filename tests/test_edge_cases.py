# -*- coding: utf-8 -*-
"""
Tests unitaires de non-régression (WAV 24-bit, .aup3 48kHz, JSON corrompu, stéréo).

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

from audio_transcriber import SpeakerDiarizer, TranscriptSegment
from audio_transcriber.audio_loader import AudioSignalLoader


class TestEdgeCasesAndRegressions(unittest.TestCase):
    """Couvre les formats PCM 24-bit, le taux d'échantillonnage .aup3 et le JSON."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_edges_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_load_24bit_wav_and_aup3_custom_rate(self) -> None:
        wav24: str = os.path.join(self.tmp_dir, "pcm24.wav")
        with wave.open(wav24, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(3)
            wf.setframerate(22050)
            wf.writeframes(b"\x00\x00\x40\x00\x00\xc0")
        samples, rate = AudioSignalLoader.load_audio(wav24)
        self.assertEqual(rate, 22050)
        self.assertEqual(samples.shape, (2, 1))
        first_val, second_val = samples.ravel().tolist()
        self.assertAlmostEqual(first_val, 0.5, places=4)
        self.assertAlmostEqual(second_val, -0.5, places=4)

        aup3_48k: str = os.path.join(self.tmp_dir, "rate48k.aup3")
        conn = sqlite3.connect(aup3_48k)
        conn.execute("CREATE TABLE project (id INTEGER PRIMARY KEY, dict BLOB)")
        conn.execute("CREATE TABLE sampleblocks (blockid INTEGER PRIMARY KEY, samples BLOB)")
        conn.execute("INSERT INTO project (id, dict) VALUES (1, ?)", (b'<project rate="48000"/>',))
        arr = np.zeros(120, dtype=np.float32)
        conn.execute("INSERT INTO sampleblocks (blockid, samples) VALUES (1, ?)", (arr.tobytes(),))
        conn.commit()
        conn.close()
        _, parsed_rate = AudioSignalLoader.load_audio(aup3_48k)
        self.assertEqual(parsed_rate, 48000)

    def test_corrupted_profiles_json_and_duplicate_rename(self) -> None:
        bad_json: str = os.path.join(self.tmp_dir, "corrupted.json")
        with open(bad_json, "w", encoding="utf-8") as fh:
            fh.write("{invalid_json")
        diarizer = SpeakerDiarizer(profiles_path=bad_json)
        self.assertEqual(diarizer.load_profiles(), 0)
        segs = [TranscriptSegment(start=0.0, end=1.0, text="Test")]
        self.assertEqual(diarizer.assign_speakers("", segs), ["Interlocuteur_1"])
        self.assertFalse(diarizer.rename_speaker("Interlocuteur_1", "Interlocuteur_1"))


if __name__ == "__main__":
    unittest.main()
