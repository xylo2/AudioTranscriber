# -*- coding: utf-8 -*-
"""
Réparation des URLs tronquées par l'affichage web et purge des artefacts temporaires.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
from pathlib import Path
import re
from typing import Dict, Set, Tuple

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS: Set[str] = {
    ".venv", "venv", "env", "__pycache__", ".git", ".idea", ".vscode",
    "build", "dist", "node_modules", ".watch_clipboard", ".native_host",
}
TARGET_EXTS: Set[str] = {".py", ".js", ".html", ".css", ".json", ".md", ".ini", ".txt"}
TEMP_ARTIFACTS: Tuple[str, ...] = ("iaexport", "verification_liens.txt")


def get_canonical_segments() -> Tuple[str, str, str]:
    """Retourne le schéma HTTPS et les URLs canoniques de référence."""
    scheme: str = "https"
    google_base: str = scheme + "://" + "www." + "google" + ".com"
    github_base: str = scheme + "://" + "github" + ".com"
    return scheme, google_base, github_base


def cleanup_temp_files(root_dir: Path = ROOT_DIR) -> int:
    """Supprime les fichiers temporaires résiduels à la racine du dossier cible."""
    removed: int = 0
    for name in TEMP_ARTIFACTS:
        candidate: Path = root_dir / name
        if candidate.is_file():
            candidate.unlink()
            removed += 1
    return removed
def _repair_content(text: str) -> Tuple[str, int]:
    """Corrige les préfixes d'URL altérés et normalise les domaines cibles."""
    scheme, google_base, github_base = get_canonical_segments()
    total_fixes: int = 0

    broken_colon_slash = re.compile(re.escape(scheme) + r":/[:/]+([a-zA-Z0-9.-]+)")
    text, n1 = broken_colon_slash.subn(scheme + r"://\1", text)
    total_fixes += n1

    bare_google = re.compile(re.escape(scheme) + r"://" + r"google\.com\b")
    text, n2 = bare_google.subn(google_base, text)
    total_fixes += n2

    bare_github = re.compile(re.escape(scheme) + r"://www\." + r"github\.com\b")
    text, n3 = bare_github.subn(github_base, text)
    total_fixes += n3

    ci_url: str = github_base + "/xylo2/AudioTranscriber/actions/workflows/ci.yml"
    broken_badge: str = f"[![Tests unitaires et couverture]({github_base})]({github_base})"
    fixed_badge: str = f"[![Tests unitaires et couverture]({ci_url}/badge.svg)]({ci_url})"
    if broken_badge in text:
        text = text.replace(broken_badge, fixed_badge)
        total_fixes += 1
    return text, total_fixes


def repair_tools_urls(root_dir: Path = ROOT_DIR) -> Dict[str, int]:
    """Parcourt l'arborescence et répare les URLs altérées dans les fichiers texte."""
    cleanup_temp_files(root_dir)
    results: Dict[str, int] = {}
    for curr_root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        curr_path: Path = Path(curr_root)
        for fname in sorted(files):
            fpath: Path = curr_path / fname
            if fpath.suffix.lower() not in TARGET_EXTS:
                continue
            try:
                original: str = fpath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            repaired, count = _repair_content(original)
            rel_key: str = fpath.relative_to(root_dir).as_posix()
            modified: int = 1 if (count > 0 and repaired != original) else 0
            results[rel_key] = modified
            if modified:
                fpath.write_text(repaired, encoding="utf-8", newline="\n")
    return results


if __name__ == "__main__":
    for rel_file, changed in repair_tools_urls().items():
        if changed:
            print(f"[fix_urls] Réparé : {rel_file}")
