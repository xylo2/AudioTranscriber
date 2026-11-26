# -*- coding: utf-8 -*-
"""
Construit les paquets distribuables (.whl et .tar.gz) de la librairie.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import shutil
import subprocess
import sys

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR: str = os.path.join(ROOT_DIR, "dist")


def clean_build_dirs() -> None:
    """Supprime les anciens artefacts de compilation dans dist/ et build/."""
    for folder_name in ("dist", "build"):
        target: str = os.path.join(ROOT_DIR, folder_name)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
    src_dir: str = os.path.join(ROOT_DIR, "src")
    if os.path.isdir(src_dir):
        for entry in os.listdir(src_dir):
            if entry.endswith(".egg-info"):
                shutil.rmtree(os.path.join(src_dir, entry), ignore_errors=True)


def build_wheel() -> int:
    """Génère le fichier .whl et l'archive source .tar.gz dans dist/."""
    clean_build_dirs()
    cmd = [sys.executable, "-m", "build", "--outdir", DIST_DIR]
    proc = subprocess.run(cmd, cwd=ROOT_DIR, check=False)
    if proc.returncode != 0:
        print(
            "[ERREUR] Échec du build. Vérifiez que 'build' est installé "
            "(pip install -r requirements.txt).",
            file=sys.stderr,
        )
        return proc.returncode

    if os.path.isdir(DIST_DIR):
        print("\n=== ARTEFACTS GÉNÉRÉS DANS dist/ ===", flush=True)
        for name in sorted(os.listdir(DIST_DIR)):
            print(f"  - dist/{name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(build_wheel())
