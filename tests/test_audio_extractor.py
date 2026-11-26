# -*- coding: utf-8 -*-
"""
Tests unitaires de l'extraction de piste audio vidéo (remux et repli WAV).

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import shutil
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

from audio_transcriber import (
    AudioTranscriber,
    __version__,
    extract_audio,
    infer_audio_extension,
)
from audio_transcriber.audio_extractor import (
    _probe_audio_codec,
    _remux_audio_stream,
    _write_pcm_wav,
)


class TestAudioExtractor(unittest.TestCase):
    """Vérifie la version, la déduction d'extension, le remux et le repli WAV."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_extract_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_package_version_and_infer_audio_extension(self) -> None:
        self.assertEqual(__version__, "0.2.0")
        self.assertEqual(infer_audio_extension("rush.mp4", codec_name="aac"), ".m4a")
        self.assertEqual(infer_audio_extension("clip.webm", codec_name="opus"), ".opus")
        self.assertEqual(infer_audio_extension("film.mkv", codec_name="ac3"), ".wav")
        self.assertEqual(infer_audio_extension("video.mov"), ".m4a")
        self.assertEqual(infer_audio_extension("cam.mts"), ".wav")
    def test_extract_audio_remux_wav_fallback_and_errors(self) -> None:
        with self.assertRaises(FileNotFoundError):
            AudioTranscriber.extract_audio(os.path.join(self.tmp_dir, "absent.mp4"))

        mp4_path: str = os.path.join(self.tmp_dir, "interview.mp4")
        with open(mp4_path, "wb") as fh:
            fh.write(b"FAKE_MP4")

        class _FakePacket:
            def __init__(self, dts: object) -> None:
                self.dts = dts
                self.stream = None

        class _FakeInContainer:
            streams = SimpleNamespace(
                audio=[SimpleNamespace(codec_context=SimpleNamespace(name="aac"))]
            )

            def demux(self, _stream):
                yield _FakePacket(None)
                yield _FakePacket(1)

            def close(self) -> None:
                pass

        class _FakeOutContainer:
            def __init__(self, target: str) -> None:
                self._target = target

            def add_stream_from_template(self, _stream):
                return SimpleNamespace()

            def mux(self, _packet) -> None:
                with open(self._target, "wb") as out_f:
                    out_f.write(b"ADTS_AAC_BYTES")

            def close(self) -> None:
                pass

        def _fake_av_open(path: str, mode: str = "r"):
            return _FakeOutContainer(path) if mode == "w" else _FakeInContainer()

        fake_av = SimpleNamespace(open=_fake_av_open)
        with patch.dict(sys.modules, {"av": fake_av}):
            out_m4a: str = AudioTranscriber.extract_audio(mp4_path, output_path=self.tmp_dir)
        self.assertTrue(out_m4a.endswith("interview.m4a"))

        explicit_mp3: str = os.path.join(self.tmp_dir, "force.mp3")
        with patch("audio_transcriber.audio_extractor._remux_audio_stream", return_value=False):
            with self.assertRaises(RuntimeError):
                extract_audio(mp4_path, output_path=explicit_mp3)

        sr: int = 16000
        sig_1d = np.sin(2.0 * np.pi * 440.0 * np.linspace(0.0, 0.25, sr // 4))
        wav_1d: str = os.path.join(self.tmp_dir, "mono_1d.wav")
        _write_pcm_wav(sig_1d.astype(np.float32), sr, wav_1d)
        with wave.open(wav_1d, "rb") as wf:
            self.assertEqual((wf.getnchannels(), wf.getframerate()), (1, sr))

        with patch.dict(sys.modules, {"av": None}):
            with patch(
                "audio_transcriber.audio_loader.AudioSignalLoader.load_audio",
                return_value=(sig_1d.reshape(-1, 1).astype(np.float32), sr),
            ):
                out_wav: str = extract_audio(mp4_path)
            with patch(
                "audio_transcriber.audio_loader.AudioSignalLoader.load_audio",
                return_value=(np.zeros((0, 1), dtype=np.float32), sr),
            ):
                with self.assertRaises(ValueError):
                    extract_audio(mp4_path)
        self.assertTrue(out_wav.endswith("interview.wav"))
