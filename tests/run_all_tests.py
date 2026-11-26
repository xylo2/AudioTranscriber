# -*- coding: utf-8 -*-
"""
Orchestrateur parallèle des tests unitaires et du calcul de couverture.

License: GNU General Public License v3.0 (GPL-3.0-or-later)
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import io
import os
import sys
import tempfile
import time
import unittest
import warnings
from typing import Any, Dict, List, Optional, Tuple

TESTS_DIR: str = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR: str = os.path.dirname(TESTS_DIR)
SRC_DIR: str = os.path.join(ROOT_DIR, "src")
for path_item in (ROOT_DIR, SRC_DIR):
    if path_item not in sys.path:
        sys.path.insert(0, path_item)


class TimedTextTestResult(unittest.TextTestResult):
    """Enregistre la durée individuelle de chaque test unitaire."""

    def __init__(self, stream: Any, descriptions: bool, verbosity: int) -> None:
        super().__init__(stream, descriptions, verbosity)
        self._test_starts: Dict[str, float] = {}
        self.test_timings: List[Tuple[float, str]] = []

    def startTest(self, test: unittest.TestCase) -> None:
        self._test_starts[test.id()] = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase) -> None:
        start_t: Optional[float] = self._test_starts.pop(test.id(), None)
        if start_t is not None:
            self.test_timings.append((time.perf_counter() - start_t, test.id()))
        super().stopTest(test)


def _build_coverage_obj(data_file: Optional[str] = None) -> Optional[Any]:
    try:
        import coverage  # type: ignore[import-not-found]
    except ImportError:
        return None
    kw: Dict[str, Any] = {
        "source": [os.path.join(SRC_DIR, "audio_transcriber")],
        "omit": ["*/__init__.py", "*/tests/*", "*/.venv/*", "*/venv/*"],
    }
    if data_file:
        kw["data_file"] = data_file
    return coverage.Coverage(**kw)
def _run_single_test_module(
    mod_name: str, cov_dir: Optional[str]
) -> Tuple[str, bool, int, str, List[Tuple[float, str]], Optional[str]]:
    cov_file: Optional[str] = (
        os.path.join(cov_dir, f".coverage.{mod_name}") if cov_dir else None
    )
    cov = _build_coverage_obj(data_file=cov_file)
    if cov is not None:
        cov.start()
    buf = io.StringIO()
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(f"tests.{mod_name}")
    runner = unittest.TextTestRunner(
        stream=buf, verbosity=1, warnings="default", resultclass=TimedTextTestResult
    )
    result: Any = runner.run(suite)
    if cov is not None:
        cov.stop()
        cov.save()
    return (
        mod_name,
        result.wasSuccessful(),
        result.testsRun,
        buf.getvalue(),
        list(getattr(result, "test_timings", [])),
        cov_file,
    )


def _format_coverage_summary(cov: Any, show_missing: bool = True) -> None:
    buf = io.StringIO()
    total_pct: float = cov.report(file=buf, show_missing=True, skip_empty=True)
    rows: List[Tuple[float, str, int, int, str]] = []
    missing_details: List[str] = []
    for line in buf.getvalue().splitlines():
        parts = line.split()
        first_col = next(iter(parts), "")
        if len(parts) < 4 or first_col in {"Name", "TOTAL"} or line.startswith("-"):
            continue
        pct_idx: int = next((i for i, p in enumerate(parts) if p.endswith("%")), -1)
        if pct_idx < 3:
            continue
        try:
            pct = float(parts[pct_idx].rstrip("%"))
            stmts, miss = int(parts[pct_idx - 2]), int(parts[pct_idx - 1])
        except ValueError:
            continue
        rel_path = os.path.relpath(" ".join(parts[: pct_idx - 2]), ROOT_DIR).replace("\\", "/")
        miss_ranges: str = " ".join(parts[pct_idx + 1 :]).strip()
        rows.append((pct, rel_path, stmts, miss, miss_ranges))
        if miss > 0 and miss_ranges:
            missing_details.append(f"- {rel_path} ({pct:.1f}%) : lignes {miss_ranges}")
    rows.sort()
    print(f"{'Module':<46} | {'Couv.':>6} | {'Statut':<7} | {'Lignes'}", flush=True)
    print("-" * 76, flush=True)
    for pct, rel_path, stmts, miss, _ in rows:
        status = "OK" if pct >= 85.0 else ("MOYEN" if pct >= 70.0 else "BAS")
        print(f"{rel_path:<46} | {pct:5.1f}% | {status:<7} | {stmts - miss}/{stmts}", flush=True)
    print("-" * 76, flush=True)
    print(f"{'COUVERTURE GLOBALE':<46} | {total_pct:5.1f}%", flush=True)
    if show_missing and missing_details:
        print("\nLignes non couvertes :", flush=True)
        for item in missing_details:
            print(item, flush=True)
def _print_timing_summary(timings: List[Tuple[float, str]], unit_s: float, total_s: float) -> None:
    print("\n=== CHRONOMÉTRAGE DES TESTS ===", flush=True)
    sorted_t = sorted(timings, key=lambda pair: -next(iter(pair)))
    for rank, (dur, test_id) in enumerate(sorted_t[:5], start=1):
        print(f"  {rank}. {test_id.split('.')[-1]:<52} : {dur:6.2f}s", flush=True)
    print(f"TEMPS TESTS : Unitaires {unit_s:.2f}s | Total {total_s:.2f}s", flush=True)


def main() -> None:
    t_global = time.perf_counter()
    warnings.simplefilter("default")
    parser = argparse.ArgumentParser(description="Lance les tests en parallèle.")
    parser.add_argument("--no-missing", action="store_true")
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--max-errors", type=int, default=5)
    parser.add_argument("-j", "--workers", type=int, default=min(4, os.cpu_count() or 2))
    args = parser.parse_args()

    mod_names = sorted(
        fn[:-3] for fn in os.listdir(TESTS_DIR)
        if fn.startswith("test_") and fn.endswith(".py")
    )
    print(f"=== 1. EXÉCUTION PARALLÈLE ({len(mod_names)} modules, {args.workers} workers) ===", flush=True)
    timings: List[Tuple[float, str]] = []
    total_run = 0
    failed_modules = 0
    t_unit = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="cov_parallel_") as cov_dir:
        cov_files: List[str] = []
        pool = ProcessPoolExecutor(max_workers=max(1, args.workers))
        try:
            futs = [pool.submit(_run_single_test_module, m, cov_dir) for m in mod_names]
            for fut in as_completed(futs):
                mod_n, ok, cnt, out_txt, mod_timings, c_file = fut.result()
                total_run += cnt
                timings.extend(mod_timings)
                if c_file and os.path.isfile(c_file):
                    cov_files.append(c_file)
                if not ok:
                    failed_modules += 1
                    print(f"\n[ÉCHEC] {mod_n}\n{out_txt}", flush=True)
                    if args.max_errors > 0 and failed_modules >= args.max_errors:
                        for pending in futs:
                            pending.cancel()
                        break
                else:
                    print(f"  [OK] {mod_n} ({cnt} test(s))", flush=True)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        unit_s = time.perf_counter() - t_unit
        if failed_modules > 0:
            _print_timing_summary(timings, unit_s, time.perf_counter() - t_global)
            sys.exit(1)

        final_cov = _build_coverage_obj(data_file=os.path.join(ROOT_DIR, ".coverage"))
        if final_cov is not None and cov_files:
            final_cov.combine(data_paths=cov_files)
            print(f"\n=== 3. COUVERTURE ({total_run} tests unitaires) ===", flush=True)
            _format_coverage_summary(final_cov, show_missing=not args.no_missing)

    _print_timing_summary(timings, unit_s, time.perf_counter() - t_global)


if __name__ == "__main__":
    main()
