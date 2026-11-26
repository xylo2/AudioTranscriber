# -*- coding: utf-8 -*-
"""
Tests unitaires de la persistance et reconnaissance inter-fichiers des voix.

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

from audio_transcriber import AudioTranscriber, SpeakerDiarizer, TranscriberConfig


def _synth_formant_voice(
    f0: float,
    formants: tuple[float, float],
    duration: float = 1.2,
    sample_rate: int = 16000,
    leading_silence: float = 0.25,
) -> np.ndarray:
    """Simule une voix avec silence d'attaque, fondamental et formants modulés."""
    n_sil = int(leading_silence * sample_rate)
    n_voiced = max(1, int((duration - leading_silence) * sample_rate))
    t = np.linspace(0.0, duration - leading_silence, n_voiced, endpoint=False)
    f1, f2 = formants
    env = 0.65 + 0.35 * np.sin(2.0 * np.pi * 3.5 * t)
    sig = env * (
        0.55 * np.sin(2.0 * np.pi * f0 * t)
        + 0.30 * np.sin(2.0 * np.pi * f1 * t)
        + 0.15 * np.sin(2.0 * np.pi * f2 * t)
    )
    return np.concatenate([np.zeros(n_sil), sig * 0.6])


def _save_mono_wav(path: str, signal: np.ndarray, sample_rate: int = 16000) -> None:
    pcm = np.clip(signal * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


class TestSpeakerProfilesPersistence(unittest.TestCase):
    """Vérifie la sauvegarde JSON atomique des profils vocaux et le renommage."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_profiles_")
        self.profiles_json: str = os.path.join(self.tmp_dir, "voices.json")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    def test_cross_file_speaker_recognition_and_rename(self) -> None:
        sr: int = 16000
        voice_a = _synth_formant_voice(120.0, (480.0, 1150.0), duration=1.2, sample_rate=sr)
        voice_b = _synth_formant_voice(235.0, (1950.0, 3400.0), duration=1.2, sample_rate=sr)

        wav_1: str = os.path.join(self.tmp_dir, "appel_1.wav")
        wav_2: str = os.path.join(self.tmp_dir, "appel_2.wav")
        _save_mono_wav(wav_1, np.concatenate([voice_a, voice_b]), sample_rate=sr)
        _save_mono_wav(wav_2, np.concatenate([voice_b, voice_a]), sample_rate=sr)

        fake_model_1 = SimpleNamespace(
            transcribe=lambda *_a, **_kw: (
                [
                    SimpleNamespace(start=0.0, end=1.2, text="Premier fichier voix A."),
                    SimpleNamespace(start=1.2, end=2.4, text="Premier fichier voix B."),
                ],
                SimpleNamespace(language="fr", duration=2.4),
            )
        )
        cfg = TranscriberConfig(
            similarity_threshold=0.90,
            profiles_path=self.profiles_json,
        )
        engine_1 = AudioTranscriber(config=cfg, model_override=fake_model_1)
        res_1 = engine_1.transcribe(wav_1)
        self.assertEqual(res_1.speakers, ["Interlocuteur_1", "Interlocuteur_2"])
        self.assertTrue(os.path.isfile(self.profiles_json))

        # Renommage persistant du premier interlocuteur avant le second fichier
        self.assertTrue(engine_1.diarizer.rename_speaker("Interlocuteur_1", "Alice"))

        fake_model_2 = SimpleNamespace(
            transcribe=lambda *_a, **_kw: (
                [
                    SimpleNamespace(start=0.0, end=1.2, text="Second fichier voix B."),
                    SimpleNamespace(start=1.2, end=2.4, text="Second fichier voix A."),
                ],
                SimpleNamespace(language="fr", duration=2.4),
            )
        )
        engine_2 = AudioTranscriber(
            config=TranscriberConfig(similarity_threshold=0.90),
            model_override=fake_model_2,
        )
        engine_2.config.profiles_path = self.profiles_json
        res_2 = engine_2.transcribe(wav_2)
        seg_first, seg_second = res_2.segments
        self.assertEqual(seg_first.speaker, "Interlocuteur_2")
        self.assertEqual(seg_second.speaker, "Alice")

    def test_manual_save_and_load_profiles(self) -> None:
        diarizer = SpeakerDiarizer(profiles_path=self.profiles_json)
        self.assertEqual(diarizer.load_profiles(), 0)
        self.assertFalse(diarizer.rename_speaker("Inconnu", "Bob"))
        saved = diarizer.save_profiles()
        self.assertTrue(os.path.isfile(saved))


if __name__ == "__main__":
    unittest.main()
