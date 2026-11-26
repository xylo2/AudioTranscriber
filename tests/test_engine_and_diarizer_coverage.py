# -*- coding: utf-8 -*-
"""
Tests complémentaires de couverture pour config, engine et diarizer.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import shutil
import sys
import tempfile
import threading
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

from audio_transcriber import (
    AudioTranscriber,
    SpeakerDiarizer,
    TranscriberConfig,
    TranscriptSegment,
)


class TestEngineAndDiarizerCoverage(unittest.TestCase):
    """Couvre le cache Whisper, stop_event, on_segment et la saturation locuteurs."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_cov_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_lazy_whisper_model_fallback_and_callbacks(self) -> None:
        cache_path: str = os.path.join(self.tmp_dir, "whisper_cache")
        cfg = TranscriberConfig(cache_dir=cache_path)
        calls: list[bool] = []

        def _fake_whisper(_size: str, **kw):
            calls.append(bool(kw.get("local_files_only")))
            if kw.get("local_files_only"):
                raise RuntimeError("Modèle absent du cache local")
            return SimpleNamespace(transcribe=lambda *_a, **_kw: ([], None))

        fake_fw = SimpleNamespace(WhisperModel=_fake_whisper)
        with patch.dict(sys.modules, {"faster_whisper": fake_fw}):
            engine = AudioTranscriber(config=cfg)
            _ = engine.model
        self.assertEqual(calls, [True, False])
        self.assertTrue(os.path.isdir(cache_path))
    def test_stop_event_and_on_segment_callback(self) -> None:
        wav_path: str = os.path.join(self.tmp_dir, "short.wav")
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(np.zeros(16000, dtype=np.int16).tobytes())

        stop_evt = threading.Event()
        seen_texts: list[str] = []

        def _on_seg(seg: TranscriptSegment) -> None:
            seen_texts.append(seg.text)
            stop_evt.set()

        fake_segs = [
            SimpleNamespace(start=0.0, end=0.5, text="   "),
            SimpleNamespace(start=0.0, end=0.5, text="Premier mot"),
            SimpleNamespace(start=0.5, end=1.0, text="Ignoré après stop"),
        ]
        fake_model = SimpleNamespace(
            transcribe=lambda *_a, **_kw: (fake_segs, SimpleNamespace(language="fr", duration=0.0))
        )
        engine = AudioTranscriber(model_override=fake_model)
        res = engine.transcribe(wav_path, stop_event=stop_evt, on_segment=_on_seg)
        self.assertEqual(seen_texts, ["Premier mot"])
        self.assertAlmostEqual(res.duration, 0.5, places=3)

    def test_diarizer_max_speakers_cap_and_silent_segments(self) -> None:
        sr: int = 16000
        t = np.linspace(0.0, 0.5, sr // 2, endpoint=False)
        sig1 = np.sin(2.0 * np.pi * 120.0 * t) * 0.5
        sig2 = (np.sin(2.0 * np.pi * 2400.0 * t) + 0.5 * np.sin(2.0 * np.pi * 4100.0 * t)) * 0.4
        silence = np.zeros(sr // 2)
        wav_path: str = os.path.join(self.tmp_dir, "cap.wav")
        pcm = np.clip(np.concatenate([silence, sig1, sig2]) * 32767.0, -32768, 32767).astype(np.int16)
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())

        diarizer = SpeakerDiarizer(max_speakers=1, similarity_threshold=0.99)
        self.assertEqual(diarizer.assign_speakers(wav_path, []), [])
        segs = [
            TranscriptSegment(start=0.0, end=0.5, text="Silence"),
            TranscriptSegment(start=0.5, end=1.0, text="Voix 1"),
            TranscriptSegment(start=1.0, end=1.5, text="Voix 2"),
        ]
        speakers = diarizer.assign_speakers(wav_path, segs)
        self.assertEqual(speakers, ["Interlocuteur_1"])
        diarizer.clear_profiles()
        with self.assertRaises(ValueError):
            diarizer.save_profiles("")


if __name__ == "__main__":
    unittest.main()
