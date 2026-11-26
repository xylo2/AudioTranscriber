# -*- coding: utf-8 -*-
"""
Lanceur de tests unifié avec presse-papiers et rapport de couverture.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import os
import re
import subprocess
import sys
from typing import List, Optional, Set, Tuple

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

EXC_PREFIXES = (
    "AssertionError", "AttributeError", "TypeError", "ValueError",
    "KeyError", "IndexError", "OSError", "FileNotFoundError",
    "RuntimeError", "ImportError", "ZeroDivisionError", "Exception",
)


def copy_to_clipboard(text: str) -> bool:
    """Copie une chaîne UTF-8 dans le presse-papiers système."""
    if not text:
        return False
    if os.name == "nt":
        ps = (
            "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
            "Set-Clipboard -Value ([Console]::In.ReadToEnd())"
        )
        return subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            input=text.encode("utf-8"),
            check=False,
        ).returncode == 0
    cmd = ["pbcopy"] if sys.platform == "darwin" else ["xclip", "-selection", "clipboard"]
    try:
        return subprocess.run(cmd, input=text, text=True, encoding="utf-8", check=False).returncode == 0
    except FileNotFoundError:
        return False


def extract_warnings_and_console_errors(raw_output: str) -> str:
    """Extrait les avertissements Python uniques de la sortie des tests."""
    warn_re = re.compile(
        r"(?:ResourceWarning|DeprecationWarning|RuntimeWarning|UserWarning|SyntaxWarning)\s*:.*"
    )
    found: List[str] = []
    seen: Set[str] = set()
    for ln in raw_output.splitlines():
        s: str = ln.strip()
        if warn_re.search(s) and s not in seen:
            seen.add(s)
            found.append(s)
    return "\n".join(found)
def _parse_failure_block(blk: List[str], root_prefix: str) -> Tuple[str, str]:
    """Compacte un bloc FAIL/ERROR unittest en signature et ligne lisible."""
    header: str = next(iter(blk))
    err_line: str = next(
        (ln.strip() for ln in reversed(blk) if ln.strip().startswith(EXC_PREFIXES)),
        blk[-1].strip(),
    )
    loc_hint: str = ""
    for idx, ln in enumerate(blk):
        st: str = ln.lstrip()
        if st.startswith('File "') and root_prefix in ln:
            m = re.search(r'File "([^"]+)", line (\d+)', st)
            if m:
                rel_f: str = os.path.relpath(m.group(1), ROOT_DIR).replace("\\", "/")
                loc_hint = f"LOC: {rel_f}:{m.group(2)}"
            if idx + 1 < len(blk) and not blk[idx + 1].lstrip().startswith(('File "', "---", "===")):
                loc_hint += f" | CODE: {blk[idx + 1].strip()}"
    sig: str = f"{loc_hint}|{err_line[:120]}"
    formatted: str = " | ".join(p for p in (header, loc_hint, err_line[:220]) if p)
    return sig, formatted


def compact_error_report(raw_output: str) -> str:
    """Déduplique et résume les erreurs unittest pour le presse-papiers."""
    sections: List[str] = re.split(r"(?m)^={60,}\s*$", raw_output)
    out: List[str] = []
    seen: Set[str] = set()
    root_prefix: str = os.path.abspath(ROOT_DIR)
    summary_line: str = ""
    for sec in sections:
        blk: List[str] = [ln.rstrip() for ln in sec.strip().splitlines() if ln.strip()]
        if not blk:
            continue
        first_ln: str = next(iter(blk))
        if first_ln.startswith(("FAIL:", "ERROR:")):
            sig, formatted = _parse_failure_block(blk, root_prefix)
            if sig in seen:
                out.append(f"[DOUBLON] {first_ln} -> {formatted.split(' | ')[-1][:140]}")
            else:
                seen.add(sig)
                out.append(formatted)
        for ln in blk:
            s: str = ln.strip()
            if s.startswith("Ran "):
                summary_line = s
            elif s.startswith(("FAILED", "OK")) and summary_line:
                summary_line = f"{summary_line} | {s}"
    if summary_line:
        out.append(summary_line)
    return "\n".join(out).strip() or raw_output[-2500:].strip()
def extract_coverage_section(raw_output: str) -> str:
    """Extrait le résumé de couverture et les lignes manquantes du rapport."""
    lines: List[str] = raw_output.splitlines()
    global_pcts: List[float] = []
    incomplete_rows: List[str] = []
    missing_lines: List[str] = []
    in_cov = in_missing = False
    for ln in lines:
        s: str = ln.strip()
        if "=== 3. COUVERTURE" in s:
            in_cov, in_missing = True, False
            continue
        if s.startswith("=== CHRONOMÉTRAGE") or s.startswith("TEMPS TESTS :"):
            in_cov = in_missing = False
            continue
        m_glob = re.match(r"^COUVERTURE GLOBALE\s*[|:]\s*([0-9]+(?:\.[0-9]+)?)%", s)
        if m_glob:
            global_pcts.append(float(m_glob.group(1)))
            continue
        if not in_cov:
            continue
        if s == "Lignes non couvertes :":
            in_missing = True
            continue
        if in_missing and s.startswith("- "):
            missing_lines.append(s)
        elif "|" in s and not s.startswith("Module"):
            parts: List[str] = [p.strip() for p in s.split("|")]
            if len(parts) >= 4 and next(iter(parts[1:2]), "") != "100.0%":
                incomplete_rows.append(s)
    if not global_pcts:
        return ""
    out: List[str] = [f"COUVERTURE GLOBALE : {global_pcts[-1]:.1f}%"]
    if incomplete_rows:
        out.extend(["\nModules incomplets (< 100%) :", *incomplete_rows])
    if missing_lines:
        out.extend(["\nLignes non couvertes :", *missing_lines])
    return "\n".join(out).strip()


def _get_arg(argv: List[str], flag: str) -> Optional[str]:
    """Retourne la valeur associée à un drapeau CLI s'il est présent."""
    if flag in argv:
        idx: int = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def main() -> int:
    """Purge les artefacts, exécute les tests et copie le rapport au presse-papiers."""
    from tools.fix_urls import repair_tools_urls

    repair_tools_urls()
    use_clip: bool = "--no-clipboard" not in sys.argv
    report_file: Optional[str] = _get_arg(sys.argv, "--report-file")
    coverage_file: Optional[str] = _get_arg(sys.argv, "--coverage-file")
    max_err: str = _get_arg(sys.argv, "--max-errors") or "5"
    runner_script: str = os.path.join(ROOT_DIR, "tests", "run_all_tests.py")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    cmd: List[str] = [sys.executable, "-u", runner_script, "--max-errors", max_err]
    if "--fast" in sys.argv:
        cmd.append("--fast")
    proc = subprocess.Popen(cmd, cwd=ROOT_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    captured: List[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        captured.append(line)
    rc: int = proc.wait()
    combined: str = "".join(captured)
    has_err: bool = rc != 0 or any(ln.strip().startswith(("FAIL:", "ERROR:", "FAILED", "Traceback (most recent call last):")) for ln in combined.splitlines())
    warns: str = extract_warnings_and_console_errors(combined)
    ok_all: bool = not has_err and not warns
    cov_text: str = extract_coverage_section(combined) if ok_all else ""
    if ok_all:
        timings = [ln.strip() for ln in combined.splitlines() if ln.strip().startswith(("TEMPS TESTS :", "1.", "2.", "3.", "4.", "5."))]
        payload = "\n".join([*(cov_text.splitlines() if cov_text else []), *timings]) or "OK : Tous les tests sont passés."
    else:
        payload = "\n\n".join([compact_error_report(combined), *([f"WARNINGS :\n{warns}"] if warns else [])])
    if report_file:
        with open(report_file, "w", encoding="utf-8") as f_r:
            f_r.write(payload + "\n")
    if coverage_file:
        with open(coverage_file, "w", encoding="utf-8") as f_c:
            f_c.write((cov_text + "\n") if cov_text else "")
    if use_clip and copy_to_clipboard(payload):
        print("\n[PRESSE-PAPIERS] Rapport copié.", flush=True)
    return 0 if ok_all else (rc or 1)


if __name__ == "__main__":
    sys.exit(main())
