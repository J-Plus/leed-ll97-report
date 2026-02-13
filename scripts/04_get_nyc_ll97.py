#!/usr/bin/env python3
"""
Download NYC LL97 emissions dataset.

Source: NYC Open Data – DOB Sustainability Compliance Map (LL97 Excel attachment).
Downloads the .xlsx file and converts it to CSV.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts_helpers import setup_logging, get_config

logger = logging.getLogger(__name__)


def main():
    config = get_config()
    setup_logging()

    logger.info("=== Step 4: Download NYC LL97 data ===")

    config.RAW_LL97.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Download the Excel file
    logger.info("Downloading LL97 xlsx from %s", config.NYC_LL97_URL)
    headers = {}
    if config.NYC_OPEN_DATA_APP_TOKEN:
        headers["X-App-Token"] = config.NYC_OPEN_DATA_APP_TOKEN

    resp = requests.get(config.NYC_LL97_URL, headers=headers, timeout=300)
    resp.raise_for_status()

    xlsx_path = config.RAW_LL97 / f"nyc_ll97_{ts}.xlsx"
    xlsx_path.write_bytes(resp.content)
    logger.info("Saved %d bytes to %s", len(resp.content), xlsx_path)

    # Convert to CSV
    df = pd.read_excel(xlsx_path, engine="openpyxl")
    csv_path = config.RAW_LL97 / f"nyc_ll97_{ts}.csv"
    df.to_csv(csv_path, index=False)
    logger.info("Converted to CSV: %d rows → %s", len(df), csv_path)


if __name__ == "__main__":
    main()
