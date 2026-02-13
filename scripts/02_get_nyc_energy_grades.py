#!/usr/bin/env python3
"""
Download NYC Energy Grades dataset (LL33 letter grades A–D).

Source: NYC Open Data – Energy and Water Data Disclosure for Local Law 33
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

    logger.info("=== Step 2: Download NYC Energy Grades ===")

    from leed_ll97_report.io import download_csv

    dest = download_csv(
        url=config.NYC_ENERGY_GRADES_URL,
        dest_dir=config.RAW_ENERGY_GRADES,
        filename="nyc_energy_grades.csv",
        app_token=config.NYC_OPEN_DATA_APP_TOKEN,
    )
    logger.info("Energy grades saved to %s", dest)


if __name__ == "__main__":
    main()
