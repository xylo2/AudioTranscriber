# -*- coding: utf-8 -*-
"""
Tests ciblés pour atteindre 100% de couverture sur audio_extractor et diarizer.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

SRC_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from audio_transcriber import SpeakerDiarizer, TranscriptSegment
from audio_transcriber.audio_extractor import (
    _probe_audio_codec,
    _remux_audio_stream,
)


class TestCoverageBoost(unittest.TestCase):
    """Couvre les branches internes résiduelles d'extraction et de diarisation."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_boost_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_extractor_internal_error_branches(self) -> None:
        target_m4a: str = os.path.join(self.tmp_dir, "partial.m4a")
        with patch.dict(sys.modules, {"av": None}):
            self.assertFalse(_remux_audio_stream("in.mp4", target_m4a))

        class _NoAudioCtr:
            streams = SimpleNamespace(audio=[])

            def close(self) -> None:
                raise RuntimeError("close err")

        fake_no_audio = SimpleNamespace(open=lambda *_a, **_kw: _NoAudioCtr())
        with patch.dict(sys.modules, {"av": fake_no_audio}):
            self.assertIsNone(_probe_audio_codec("in.mp4"))
            self.assertFalse(_remux_audio_stream("in.mp4", target_m4a))

        class _BrokenMuxCtr:
            def add_stream_from_template(self, _s):
                with open(target_m4a, "wb") as fh:
                    fh.write(b"PARTIAL")
                raise RuntimeError("mux failed")

            def close(self) -> None:
                raise RuntimeError("close out err")

        class _ValidInCtr:
            streams = SimpleNamespace(audio=[SimpleNamespace()])

            def close(self) -> None:
                pass

        def _open_broken(path: str, mode: str = "r"):
            if mode == "w":
                return _BrokenMuxCtr()
            if path == "boom.mp4":
                raise RuntimeError("probe fail")
            return _ValidInCtr()

        with patch.dict(sys.modules, {"av": SimpleNamespace(open=_open_broken)}):
            self.assertIsNone(_probe_audio_codec("boom.mp4"))
            self.assertFalse(_remux_audio_stream("in.mp4", target_m4a))
        self.assertFalse(os.path.exists(target_m4a))
    def test_diarizer_edge_branches(self) -> None:
        d = SpeakerDiarizer(max_speakers=1)
        d._labels = ["Interlocuteur_1"]
        d._centroids = [np.array([1.0, 0.0], dtype=np.float32)]
        d._counts = [1]
        self.assertEqual(d._next_speaker_label(), "Interlocuteur_2")
        self.assertEqual(
            d._match_or_register_embedding(
                np.array([0.0, 1.0], dtype=np.float32),
                excluded_labels={"Interlocuteur_1"},
            ),
            "Interlocuteur_2",
        )

        # Canal stéréo silencieux sur la fenêtre du segment -> repli _next_speaker_label
        sr: int = 16000
        t = np.linspace(0.0, 0.5, sr // 2, endpoint=False)
        left = np.concatenate([np.zeros(sr // 2), np.sin(2.0 * np.pi * 300.0 * t) * 0.6])
        right = np.concatenate([np.zeros(sr // 2), np.sin(2.0 * np.pi * 700.0 * t) * 0.6])
        stereo_samples = np.column_stack([left, right]).astype(np.float32)
        d2 = SpeakerDiarizer(max_speakers=2)
        segs = [TranscriptSegment(start=0.0, end=0.5, text="Début silencieux")]
        self.assertEqual(
            d2._assign_by_stereo_channels(stereo_samples, sr, segs),
            ["Interlocuteur_1"],
        )

        # Signature vocale : signal quasi-silencieux, trames faibles et vecteur nul
        self.assertIsNone(d2._extract_voice_signature(np.zeros(sr, dtype=np.float32), sr))
        loud_spike = np.zeros(sr, dtype=np.float32)
        loud_spike[:2048] = 1.0
        loud_spike[2048:] = 1e-4
        self.assertIsNotNone(d2._extract_voice_signature(loud_spike, sr))
        with patch("numpy.linalg.norm", return_value=0.0):
            self.assertIsNone(d2._extract_voice_signature(loud_spike, sr))


if __name__ == "__main__":
    unittest.main()
