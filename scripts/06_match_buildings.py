#!/usr/bin/env python3
"""
Match LEED buildings to NYC datasets and produce the master table.
"""

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts_helpers import setup_logging, get_config

logger = logging.getLogger(__name__)


def main(use_manual_mapping: bool = False, min_confidence: int = 50):
    config = get_config()
    setup_logging()

    logger.info("=== Step 6: Match Buildings ===")

    from leed_ll97_report.io import load_csv, save_csv
    from leed_ll97_report.matching import match_buildings, apply_manual_mapping, build_master_table

    cleaned = config.CLEANED_DIR

    # Load cleaned datasets
    leed_path = cleaned / "leed_cleaned.csv"
    grades_path = cleaned / "nyc_energy_grades_cleaned.csv"
    bench_path = cleaned / "nyc_benchmarking_cleaned.csv"
    ll97_path = cleaned / "nyc_ll97_cleaned.csv"

    if not leed_path.exists():
        logger.error("No cleaned LEED data found. Run step 05 first.")
        return

    leed_df = load_csv(leed_path)

    # Load NYC datasets (grades is primary, others supplement)
    grades_df = load_csv(grades_path) if grades_path.exists() else pd.DataFrame()
    bench_df = load_csv(bench_path) if bench_path.exists() else pd.DataFrame()
    ll97_df = load_csv(ll97_path) if ll97_path.exists() else pd.DataFrame()

    # Merge grades and benchmarking into a unified NYC dataset for matching
    # Prefer grades dataset as primary; supplement with benchmarking
    if not grades_df.empty:
        nyc_df = grades_df.copy()
    elif not bench_df.empty:
        nyc_df = bench_df.copy()
    else:
        logger.error("No NYC grade or benchmarking data available for matching.")
        return

    # If we have benchmarking data and grades data, merge extra columns
    if not grades_df.empty and not bench_df.empty and "bbl_norm" in bench_df.columns and "bbl_norm" in grades_df.columns:
        # Ensure consistent types for merge key
        nyc_df["bbl_norm"] = nyc_df["bbl_norm"].astype(str)
        bench_df["bbl_norm"] = bench_df["bbl_norm"].astype(str)
        # Add benchmarking columns not in grades
        extra_cols = [c for c in bench_df.columns if c not in grades_df.columns and c != "bbl_norm"]
        if extra_cols:
            bench_subset = bench_df[["bbl_norm"] + extra_cols].drop_duplicates(subset=["bbl_norm"])
            nyc_df = nyc_df.merge(bench_subset, on="bbl_norm", how="left")

    # Run matching
    matched_df, review_queue = match_buildings(
        leed_df=leed_df,
        nyc_df=nyc_df,
        fuzzy_address_threshold=config.FUZZY_ADDRESS_THRESHOLD,
        fuzzy_name_threshold=config.FUZZY_NAME_THRESHOLD,
        min_confidence=min_confidence,
    )

    # Apply manual mapping if requested
    if use_manual_mapping and config.MANUAL_MAPPING_PATH.exists():
        matched_df = apply_manual_mapping(matched_df, str(config.MANUAL_MAPPING_PATH))

    # Build master table
    master = build_master_table(
        leed_df=leed_df,
        nyc_grades_df=grades_df,
        nyc_bench_df=bench_df,
        nyc_ll97_df=ll97_df,
        matched_df=matched_df,
    )

    # Save outputs
    config.MATCHED_DIR.mkdir(parents=True, exist_ok=True)
    year = config.REPORT_YEAR

    save_csv(master, config.MATCHED_DIR / f"master_matched_{year}.csv")
    save_csv(review_queue, config.MATCHED_DIR / f"review_queue_{year}.csv")

    logger.info(
        "Matching complete: %d in master table, %d in review queue",
        len(master),
        len(review_queue),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--use-manual-mapping", action="store_true")
    parser.add_argument("--min-match-confidence", type=int, default=50)
    args = parser.parse_args()
    main(use_manual_mapping=args.use_manual_mapping, min_confidence=args.min_match_confidence)
