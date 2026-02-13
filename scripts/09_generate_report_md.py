#!/usr/bin/env python3
"""
Generate the annual markdown report.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts_helpers import setup_logging, get_config

logger = logging.getLogger(__name__)


def main():
    config = get_config()
    setup_logging()

    logger.info("=== Step 9: Generate Report ===")

    from leed_ll97_report.io import load_csv
    from leed_ll97_report.report import generate_report

    year = config.REPORT_YEAR
    output_dir = config.OUTPUTS_DIR / str(year)
    master_path = config.MATCHED_DIR / f"master_matched_{year}.csv"

    if not master_path.exists():
        logger.error("No master table found. Run step 06 first.")
        return

    master = load_csv(master_path)

    # Load metrics
    metrics = {}
    for name in ["headline", "leed_by_grade", "leed_level_by_grade",
                  "ll97_overage_summary", "match_coverage_stats"]:
        path = output_dir / f"{name}_{year}.csv"
        if path.exists():
            metrics[name] = load_csv(path)

    # Load degradation stats
    degradation_path = output_dir / f"degradation_stats_{year}.json"
    if degradation_path.exists():
        degradation = json.loads(degradation_path.read_text())
    else:
        degradation = {"correlation": None, "n": 0, "note": "Not computed"}

    template_path = config.REPORT_TEMPLATES_DIR / "annual_report_template.md"
    if not template_path.exists():
        template_path = None

    report_path = generate_report(
        master=master,
        metrics=metrics,
        degradation=degradation,
        year=year,
        output_dir=output_dir,
        template_path=template_path,
    )

    logger.info("Report generated: %s", report_path)


if __name__ == "__main__":
    main()
