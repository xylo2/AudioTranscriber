# -*- coding: utf-8 -*-
"""
Construit les paquets distribuables (.whl et .tar.gz) et les déploie dans les venv.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import argparse
import os
import shutil
import subprocess
import sys
from typing import List, Optional

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


def _find_latest_wheel() -> Optional[str]:
    if not os.path.isdir(DIST_DIR):
        return None
    wheels: List[str] = sorted(
        fn for fn in os.listdir(DIST_DIR) if fn.endswith(".whl")
    )
    return os.path.join(DIST_DIR, wheels[-1]) if wheels else None


def _resolve_venv_python(project_or_venv: str) -> Optional[str]:
    base: str = os.path.abspath(project_or_venv)
    candidates: List[str] = [
        base,
        os.path.join(base, "Scripts", "python.exe"),
        os.path.join(base, "bin", "python"),
        os.path.join(base, ".venv", "Scripts", "python.exe"),
        os.path.join(base, ".venv", "bin", "python"),
        os.path.join(base, "venv", "Scripts", "python.exe"),
        os.path.join(base, "venv", "bin", "python"),
    ]
    return next((c for c in candidates if os.path.isfile(c)), None)
def deploy_wheel_to_projects(wheel_path: str, targets: List[str]) -> int:
    """Installe le .whl généré dans le venv de chaque projet cible."""
    errors: int = 0
    for target in targets:
        py_bin: Optional[str] = _resolve_venv_python(target)
        if not py_bin:
            print(f"[IGNORÉ] Aucun venv Python trouvé pour : {target}", file=sys.stderr)
            errors += 1
            continue
        print(f"\n[INSTALL] {os.path.basename(wheel_path)} -> {py_bin}", flush=True)
        cmd = [py_bin, "-m", "pip", "install", "--upgrade", "--force-reinstall", wheel_path]
        proc = subprocess.run(cmd, check=False)
        if proc.returncode != 0:
            errors += 1
    return errors


def build_wheel(deploy_targets: Optional[List[str]] = None) -> int:
    """Génère le .whl et l'archive source dans dist/, puis déploie si demandé."""
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

    wheel_path: Optional[str] = _find_latest_wheel()
    if os.path.isdir(DIST_DIR):
        print("\n=== ARTEFACTS GÉNÉRÉS DANS dist/ ===", flush=True)
        for name in sorted(os.listdir(DIST_DIR)):
            print(f"  - dist/{name}", flush=True)

    if deploy_targets and wheel_path:
        return 1 if deploy_wheel_to_projects(wheel_path, deploy_targets) > 0 else 0
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Construit et déploie le paquet .whl.")
    parser.add_argument(
        "--deploy",
        nargs="+",
        default=[],
        help="Chemins vers les projets ou venv cibles (ex. ../AnonVault ../MediaReader).",
    )
    args = parser.parse_args()
    return build_wheel(deploy_targets=args.deploy)


if __name__ == "__main__":
    sys.exit(main())
