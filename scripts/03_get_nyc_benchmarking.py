#!/usr/bin/env python3
"""
Download NYC Benchmarking dataset (LL84 energy and water use disclosure).

Source: NYC Open Data – LL84 Benchmarking
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

    logger.info("=== Step 3: Download NYC Benchmarking ===")

    from leed_ll97_report.io import download_csv

    dest = download_csv(
        url=config.NYC_BENCHMARKING_URL,
        dest_dir=config.RAW_BENCHMARKING,
        filename="nyc_benchmarking.csv",
        app_token=config.NYC_OPEN_DATA_APP_TOKEN,
    )
    logger.info("Benchmarking data saved to %s", dest)


if __name__ == "__main__":
    main()
