# -*- coding: utf-8 -*-
"""
Tests unitaires de réparation des URLs et de purge des artefacts temporaires.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.fix_urls import cleanup_temp_files, repair_tools_urls


class TestFixUrls(unittest.TestCase):
    """Vérifie le nettoyage des artefacts et la normalisation des URLs."""

    def setUp(self) -> None:
        self.tmp_dir: Path = Path(tempfile.mkdtemp(prefix="test_at_urls_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_cleanup_and_repair_urls(self) -> None:
        (self.tmp_dir / "iaexport").write_text("TEMP", encoding="utf-8")
        (self.tmp_dir / "verification_liens.txt").write_text("TEMP", encoding="utf-8")
        md_file: Path = self.tmp_dir / "doc.md"
        broken_url: str = "https" + ":///" + "google" + ".com/search"
        www_gh: str = "https" + "://www." + "github" + ".com/xylo2"
        md_file.write_text(f"{broken_url}\n{www_gh}\n", encoding="utf-8")

        bin_file: Path = self.tmp_dir / "raw.txt"
        bin_file.write_bytes(b"\xff\xfe\xfd")

        res = repair_tools_urls(self.tmp_dir)
        self.assertEqual(res.get("doc.md"), 1)
        self.assertFalse((self.tmp_dir / "iaexport").exists())
        self.assertFalse((self.tmp_dir / "verification_liens.txt").exists())
        repaired_txt: str = md_file.read_text(encoding="utf-8")
        self.assertIn("www." + "google" + ".com/search", repaired_txt)
        self.assertIn("://" + "github" + ".com/xylo2", repaired_txt)
        self.assertEqual(cleanup_temp_files(self.tmp_dir), 0)


if __name__ == "__main__":
    unittest.main()
