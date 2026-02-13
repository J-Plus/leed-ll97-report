#!/usr/bin/env python3
"""
Generate all charts for the annual report.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts_helpers import setup_logging, get_config

logger = logging.getLogger(__name__)


def main():
    config = get_config()
    setup_logging()

    logger.info("=== Step 8: Generate Charts ===")

    from leed_ll97_report.io import load_csv
    from leed_ll97_report.charts import generate_all_charts

    year = config.REPORT_YEAR
    output_dir = config.OUTPUTS_DIR / str(year)
    master_path = config.MATCHED_DIR / f"master_matched_{year}.csv"

    if not master_path.exists():
        logger.error("No master table found. Run step 06 first.")
        return

    master = load_csv(master_path)

    # Load precomputed metrics
    metrics = {}
    for name in ["leed_by_grade", "leed_level_by_grade", "ll97_overage_summary", "match_coverage_stats"]:
        path = output_dir / f"{name}_{year}.csv"
        if path.exists():
            metrics[name] = load_csv(path)

    generate_all_charts(master, metrics, output_dir, year)
    logger.info("Charts complete")


if __name__ == "__main__":
    main()
