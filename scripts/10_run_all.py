#!/usr/bin/env python3
"""
End-to-end pipeline runner.

Usage:
    python scripts/10_run_all.py --year 2026
    python scripts/10_run_all.py --year 2026 --skip-download
    python scripts/10_run_all.py --year 2026 --use-manual-mapping --min-match-confidence 70
"""

import argparse
import importlib.util
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Setup ──────────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from scripts_helpers import setup_logging, get_config


logger = logging.getLogger(__name__)


def _load_script(name: str):
    """Dynamically import a numbered script module."""
    path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _get_git_hash() -> str:
    """Get current git commit hash, or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT_DIR,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except FileNotFoundError:
        return "unknown"


def write_run_log(output_dir: Path, year: int, start_time: float, args, step_times: dict):
    """Write pipeline run log."""
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run_log.txt"

    elapsed = time.time() - start_time
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        f"Pipeline Run Log",
        f"================",
        f"Timestamp: {now}",
        f"Report Year: {year}",
        f"Git Commit: {_get_git_hash()}",
        f"Python Version: {sys.version}",
        f"Total Elapsed: {elapsed:.1f}s",
        f"",
        f"Arguments:",
        f"  --year {args.year}",
        f"  --skip-download: {args.skip_download}",
        f"  --use-manual-mapping: {args.use_manual_mapping}",
        f"  --min-match-confidence: {args.min_match_confidence}",
        f"",
        f"Step Timings:",
    ]
    for step, t in step_times.items():
        lines.append(f"  {step}: {t:.1f}s")

    lines.append("")

    # Record counts
    config = get_config()
    for name, path in [
        ("LEED raw", config.RAW_LEED / "leed_nyc.csv"),
        ("Energy grades cleaned", config.CLEANED_DIR / "nyc_energy_grades_cleaned.csv"),
        ("Benchmarking cleaned", config.CLEANED_DIR / "nyc_benchmarking_cleaned.csv"),
        ("LL97 cleaned", config.CLEANED_DIR / "nyc_ll97_cleaned.csv"),
        ("Master matched", config.MATCHED_DIR / f"master_matched_{year}.csv"),
        ("Review queue", config.MATCHED_DIR / f"review_queue_{year}.csv"),
    ]:
        if path.exists():
            import pandas as pd
            try:
                count = len(pd.read_csv(path))
                lines.append(f"  {name}: {count} records")
            except Exception:
                lines.append(f"  {name}: exists (could not count)")
        else:
            lines.append(f"  {name}: not found")

    log_path.write_text("\n".join(lines))
    logger.info("Run log written to %s", log_path)


def main():
    parser = argparse.ArgumentParser(
        description="Run the LEED vs NYC Energy Grades & LL97 pipeline"
    )
    parser.add_argument("--year", type=int, default=2026, help="Report year (default: 2026)")
    parser.add_argument("--skip-download", action="store_true", help="Skip data download steps")
    parser.add_argument("--use-manual-mapping", action="store_true", help="Apply manual mapping overrides")
    parser.add_argument("--min-match-confidence", type=int, default=50, help="Min confidence for matches (default: 50)")
    args = parser.parse_args()

    setup_logging()

    # Set report year in environment for config
    os.environ["REPORT_YEAR"] = str(args.year)

    logger.info("=" * 60)
    logger.info("LEED vs NYC Energy Grades & LL97 Pipeline")
    logger.info("Report Year: %d", args.year)
    logger.info("=" * 60)

    start_time = time.time()
    step_times = {}

    # ── Step 1–4: Download data ────────────────────────────────────────────
    if not args.skip_download:
        for step_name, script_file in [
            ("01_get_leed", "01_get_leed.py"),
            ("02_get_nyc_energy_grades", "02_get_nyc_energy_grades.py"),
            ("03_get_nyc_benchmarking", "03_get_nyc_benchmarking.py"),
            ("04_get_nyc_ll97", "04_get_nyc_ll97.py"),
        ]:
            t0 = time.time()
            try:
                logger.info("Running %s ...", step_name)
                mod = _load_script(script_file)
                mod.main()
            except Exception as exc:
                logger.error("Step %s failed: %s", step_name, exc)
                logger.info("Continuing with available data...")
            step_times[step_name] = time.time() - t0
    else:
        logger.info("Skipping download steps (--skip-download)")

    # ── Step 5: Clean and normalize ────────────────────────────────────────
    t0 = time.time()
    try:
        mod = _load_script("05_clean_normalize.py")
        mod.main()
    except Exception as exc:
        logger.error("Step 05 failed: %s", exc)
        return
    step_times["05_clean_normalize"] = time.time() - t0

    # ── Step 6: Match buildings ────────────────────────────────────────────
    t0 = time.time()
    try:
        mod = _load_script("06_match_buildings.py")
        mod.main(
            use_manual_mapping=args.use_manual_mapping,
            min_confidence=args.min_match_confidence,
        )
    except Exception as exc:
        logger.error("Step 06 failed: %s", exc)
        return
    step_times["06_match_buildings"] = time.time() - t0

    # ── Step 7: Compute metrics ────────────────────────────────────────────
    t0 = time.time()
    try:
        mod = _load_script("07_compute_metrics.py")
        mod.main()
    except Exception as exc:
        logger.error("Step 07 failed: %s", exc)
        return
    step_times["07_compute_metrics"] = time.time() - t0

    # ── Step 8: Generate charts ────────────────────────────────────────────
    t0 = time.time()
    try:
        mod = _load_script("08_make_charts.py")
        mod.main()
    except Exception as exc:
        logger.error("Step 08 failed: %s", exc)
        logger.info("Continuing without charts...")
    step_times["08_make_charts"] = time.time() - t0

    # ── Step 9: Generate report ────────────────────────────────────────────
    t0 = time.time()
    try:
        mod = _load_script("09_generate_report_md.py")
        mod.main()
    except Exception as exc:
        logger.error("Step 09 failed: %s", exc)
    step_times["09_generate_report"] = time.time() - t0

    # ── Write run log ──────────────────────────────────────────────────────
    config = get_config()
    output_dir = config.OUTPUTS_DIR / str(args.year)
    write_run_log(output_dir, args.year, start_time, args, step_times)

    # ── QA checks ──────────────────────────────────────────────────────────
    logger.info("Running QA checks...")
    master_path = config.MATCHED_DIR / f"master_matched_{args.year}.csv"
    if master_path.exists():
        import pandas as pd
        master = pd.read_csv(master_path)

        # Check: grade values
        if "energy_grade" in master.columns:
            invalid = master["energy_grade"].dropna()
            invalid = invalid[~invalid.isin(["A", "B", "C", "D"])]
            if len(invalid) > 0:
                logger.warning("QA: %d records with invalid grades: %s", len(invalid), invalid.unique())

        # Check: duplicate NYC matches
        if "nyc_index" in master.columns:
            dupes = master["nyc_index"].dropna()
            dupe_count = dupes.duplicated().sum()
            if dupe_count > 0:
                logger.warning("QA: %d NYC buildings matched to multiple LEED records", dupe_count)

        # Check: extreme values
        for col in ["site_eui", "ghg_emissions_tco2e"]:
            if col in master.columns:
                vals = pd.to_numeric(master[col], errors="coerce").dropna()
                if len(vals) > 0:
                    q99 = vals.quantile(0.99)
                    extreme = (vals > q99 * 3).sum()
                    if extreme > 0:
                        logger.warning("QA: %d extreme outliers in %s", extreme, col)

    total_elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("Pipeline complete in %.1fs", total_elapsed)
    logger.info("Outputs: %s", output_dir)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
