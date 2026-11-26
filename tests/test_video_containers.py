# -*- coding: utf-8 -*-
"""
Tests unitaires des conteneurs audio/vidéo (.mov, .mts, .wma) et du filtrage.

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

from audio_transcriber import (
    AudioTranscriber,
    SUPPORTED_EXTENSIONS,
    is_supported_media,
)


class TestVideoContainersSupport(unittest.TestCase):
    """Vérifie le filtrage d'extensions et la transcription des conteneurs médias."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_video_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_supported_extensions_filter(self) -> None:
        valid_names = (
            "audio.3gp", "voix.M4A", "clip.mov", "video.mp4",
            "film.mpg", "rush.mts", "cam.wmv", "son.wma", "proj.aup3",
        )
        for ok_name in valid_names:
            self.assertTrue(is_supported_media(ok_name), ok_name)
            self.assertIn(os.path.splitext(ok_name)[-1].lower(), SUPPORTED_EXTENSIONS)

        for ko_name in ("montage.mlt", "premiere.prel", "notes.txt", "rapport.odt", "dossier", ""):
            self.assertFalse(is_supported_media(ko_name), ko_name)

    def test_transcribe_mov_mts_and_wma_containers(self) -> None:
        sr: int = 16000
        t = np.linspace(0.0, 0.5, sr // 2, endpoint=False)
        voice_1 = np.sin(2.0 * np.pi * 140.0 * t) * 0.5
        voice_2 = np.sin(2.0 * np.pi * 1650.0 * t) * 0.5

        class _MediaContainer:
            def __init__(self) -> None:
                self.streams = SimpleNamespace(audio=[SimpleNamespace(rate=sr)])

            def decode(self, audio: int = 0):
                yield SimpleNamespace(to_ndarray=lambda: voice_1.astype(np.float32))
                yield SimpleNamespace(to_ndarray=lambda: voice_2.astype(np.float32))

            def close(self) -> None:
                pass

        fake_av = SimpleNamespace(open=lambda _path: _MediaContainer())
        fake_model = SimpleNamespace(
            transcribe=lambda *_a, **_kw: (
                [
                    SimpleNamespace(start=0.0, end=0.5, text="Réplique média un."),
                    SimpleNamespace(start=0.5, end=1.0, text="Réplique média deux."),
                ],
                SimpleNamespace(language="fr", duration=1.0),
            )
        )

        for ext in (".mov", ".mts", ".wma"):
            media_path: str = os.path.join(self.tmp_dir, f"enregistrement{ext}")
            with open(media_path, "wb") as fh:
                fh.write(b"MEDIA_CONTAINER_HEADER")
            with patch.dict(sys.modules, {"av": fake_av}):
                engine = AudioTranscriber(model_override=fake_model)
                res = engine.transcribe(media_path)
            self.assertEqual(len(res.segments), 2)
            self.assertEqual(res.speakers, ["Interlocuteur_1", "Interlocuteur_2"])


if __name__ == "__main__":
    unittest.main()
