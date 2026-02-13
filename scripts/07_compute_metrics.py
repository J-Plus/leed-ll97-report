#!/usr/bin/env python3
"""
Compute summary metrics and save output CSVs.
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

    logger.info("=== Step 7: Compute Metrics ===")

    from leed_ll97_report.io import load_csv, save_csv
    from leed_ll97_report.metrics import compute_all_metrics, compute_degradation_correlation

    year = config.REPORT_YEAR
    master_path = config.MATCHED_DIR / f"master_matched_{year}.csv"

    if not master_path.exists():
        logger.error("No master table found. Run step 06 first.")
        return

    master = load_csv(master_path)
    metrics = compute_all_metrics(master, year)
    degradation = compute_degradation_correlation(master, year)

    output_dir = config.OUTPUTS_DIR / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save summary tables
    for name, df in metrics.items():
        save_csv(df, output_dir / f"{name}_{year}.csv")

    # Save degradation stats
    import json
    (output_dir / f"degradation_stats_{year}.json").write_text(
        json.dumps(degradation, indent=2)
    )

    logger.info("Metrics computation complete. Outputs in %s", output_dir)


if __name__ == "__main__":
    main()
