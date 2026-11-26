# -*- coding: utf-8 -*-
"""
Tests unitaires de la construction et du déploiement automatique du .whl.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools import build_package


class TestBuildPackage(unittest.TestCase):
    """Vérifie la résolution des venv et l'option --deploy sans build réel."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_at_build_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_resolve_venv_and_deploy_wheel(self) -> None:
        proj_win: str = os.path.join(self.tmp_dir, "AnonVault")
        py_win: str = os.path.join(proj_win, ".venv", "Scripts", "python.exe")
        os.makedirs(os.path.dirname(py_win), exist_ok=True)
        with open(py_win, "wb") as fh:
            fh.write(b"MZ")

        self.assertEqual(build_package._resolve_venv_python(proj_win), py_win)
        self.assertIsNone(build_package._resolve_venv_python(os.path.join(self.tmp_dir, "Inconnu")))

        fake_dist: str = os.path.join(self.tmp_dir, "dist")
        os.makedirs(fake_dist, exist_ok=True)
        whl_path: str = os.path.join(fake_dist, "audio_transcriber-0.2.0-py3-none-any.whl")
        with open(whl_path, "wb") as fh:
            fh.write(b"PK")

        calls: list[list[str]] = []

        def _fake_run(cmd: list[str], **_kw):
            calls.append(cmd)
            return SimpleNamespace(returncode=0)

        with patch.object(build_package, "DIST_DIR", fake_dist):
            with patch("tools.build_package.clean_build_dirs"):
                with patch("subprocess.run", side_effect=_fake_run):
                    with patch.object(sys, "argv", ["build_package.py", "--deploy", proj_win]):
                        self.assertEqual(build_package.main(), 0)
        self.assertEqual(len(calls), 2)
        self.assertIn(py_win, calls[-1])


if __name__ == "__main__":
    unittest.main()
