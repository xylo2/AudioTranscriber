# -*- coding: utf-8 -*-
"""
Tests unitaires de la diarisation stéréo/mono et de AudioTranscriber.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
import wave
import numpy as np

SRC_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from audio_transcriber import AudioTranscriber, TranscriberConfig


def _write_wav(path: str, data: np.ndarray, sample_rate: int = 16000) -> None:
    pcm = np.clip(data * 32767.0, -32768, 32767).astype(np.int16)
    channels: int = 1 if pcm.ndim == 1 else int(pcm.shape[1])
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


class TestDiarizerAndEngine(unittest.TestCase):
    """Vérifie la séparation des voix en stéréo, en mono et l'intégration moteur."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_engine_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_stereo_two_speakers_separation(self) -> None:
        sr: int = 16000
        t = np.linspace(0.0, 1.0, sr, endpoint=False)
        left = np.concatenate([np.sin(2 * np.pi * 220 * t) * 0.6, np.zeros(sr)])
        right = np.concatenate([np.zeros(sr), np.sin(2 * np.pi * 440 * t) * 0.6])
        stereo_wav: str = os.path.join(self.tmp_dir, "dialogue_stereo.wav")
        _write_wav(stereo_wav, np.column_stack([left, right]), sample_rate=sr)

        fake_segs = [
            SimpleNamespace(start=0.0, end=1.0, text="Bonjour, comment allez-vous ?"),
            SimpleNamespace(start=1.0, end=2.0, text="Très bien, merci beaucoup."),
        ]
        fake_model = SimpleNamespace(
            transcribe=lambda *_a, **_kw: (fake_segs, SimpleNamespace(language="fr", duration=2.0))
        )
        cfg = TranscriberConfig(cache_dir=os.path.join(self.tmp_dir, "cache"))
        engine = AudioTranscriber(config=cfg, model_override=fake_model)
        result = engine.transcribe(stereo_wav)

        self.assertEqual(result.speakers, ["Interlocuteur_1", "Interlocuteur_2"])
        first_seg, second_seg = result.segments
        self.assertEqual(first_seg.speaker, "Interlocuteur_1")
        self.assertEqual(second_seg.speaker, "Interlocuteur_2")

    def test_mono_distinct_pitches_separation_and_missing_file(self) -> None:
        sr: int = 16000
        t = np.linspace(0.0, 1.0, sr, endpoint=False)
        voice_low = np.sin(2 * np.pi * 130 * t) * 0.6
        voice_high = (np.sin(2 * np.pi * 1800 * t) + 0.5 * np.sin(2 * np.pi * 3400 * t)) * 0.4
        mono_wav: str = os.path.join(self.tmp_dir, "dialogue_mono.wav")
        _write_wav(mono_wav, np.concatenate([voice_low, voice_high, voice_low]), sample_rate=sr)

        fake_segs = [
            SimpleNamespace(start=0.0, end=1.0, text="Première prise de parole."),
            SimpleNamespace(start=1.0, end=2.0, text="Réponse d'une seconde voix."),
            SimpleNamespace(start=2.0, end=3.0, text="Retour de la première voix."),
        ]
        fake_model = SimpleNamespace(
            transcribe=lambda *_a, **_kw: (fake_segs, SimpleNamespace(language="fr", duration=3.0))
        )
        engine = AudioTranscriber(
            config=TranscriberConfig(similarity_threshold=0.90),
            model_override=fake_model,
        )
        result = engine.transcribe(mono_wav)
        seg1, seg2, seg3 = result.segments
        self.assertEqual(seg1.speaker, "Interlocuteur_1")
        self.assertEqual(seg2.speaker, "Interlocuteur_2")
        self.assertEqual(seg3.speaker, "Interlocuteur_1")

        with self.assertRaises(FileNotFoundError):
            engine.transcribe(os.path.join(self.tmp_dir, "absent.wav"))


if __name__ == "__main__":
    unittest.main()
