#!/usr/bin/env python3
"""
Fetch LEED-certified NYC buildings from the USGBC public project directory.

Approach priority:
  A) GBIG / USGBC public API export
  B) Controlled scrape with throttling and caching
  C) Manual export fallback – documented procedure

If automated retrieval fails, the script prints instructions for the manual
export workflow and exits gracefully.
"""

import json
import logging
import sys
from pathlib import Path

import pandas as pd
import requests

# Allow running as a standalone script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts_helpers import setup_logging, get_config

logger = logging.getLogger(__name__)

# ── Column mapping from API response to our standard fields ────────────────
LEED_COLUMN_MAP = {
    "ID": "source_id",
    "ProjectName": "building_name_raw",
    "Street": "address_raw",
    "City": "city",
    "State": "state",
    "Zip": "zip",
    "CertLevel": "leed_level",
    "CertDate": "leed_cert_year",
    "ProjectType": "project_type",
    "LEEDSystemVersionDisplayName": "leed_version",
    "IsCertified": "is_certified",
    "TotalGSF": "gross_sqft",
}


def try_api_export(config) -> pd.DataFrame | None:
    """Attempt to pull LEED data from the USGBC public search API."""
    base_url = config.LEED_API_BASE
    params = {
        "State": "NY",
        "City": "New York",
        "IsCertified": "true",
        "PageSize": 1000,
        "PageIndex": 0,
    }

    all_records = []
    try:
        while True:
            logger.info("LEED API request page %d", params["PageIndex"])
            resp = requests.get(base_url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            projects = data if isinstance(data, list) else data.get("Projects", data.get("results", []))
            if not projects:
                break

            all_records.extend(projects)
            logger.info("  fetched %d records (total so far: %d)", len(projects), len(all_records))

            if len(projects) < params["PageSize"]:
                break
            params["PageIndex"] += 1

    except (requests.RequestException, json.JSONDecodeError, KeyError) as exc:
        logger.warning("LEED API attempt failed: %s", exc)
        return None

    if not all_records:
        logger.warning("LEED API returned zero records")
        return None

    df = pd.DataFrame(all_records)
    return df


def try_gbig_csv(config) -> pd.DataFrame | None:
    """Attempt to download from GBIG open dataset if available."""
    gbig_url = "https://www.gbig.org/export/activities.csv"
    try:
        logger.info("Trying GBIG CSV export...")
        resp = requests.get(gbig_url, timeout=120, stream=True)
        resp.raise_for_status()

        dest = config.RAW_LEED / "gbig_activities.csv"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)

        df = pd.read_csv(dest, low_memory=False)
        # Filter to NYC certified projects
        if "City" in df.columns and "State" in df.columns:
            mask = (df["State"] == "NY") & (
                df["City"].str.contains("New York|Manhattan|Brooklyn|Bronx|Queens|Staten Island",
                                        case=False, na=False)
            )
            df = df[mask].copy()
        return df if len(df) > 0 else None

    except Exception as exc:
        logger.warning("GBIG download failed: %s", exc)
        return None


def normalize_leed_df(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize LEED dataframe columns regardless of source."""
    # Try to apply column map; keep whatever columns exist
    rename = {k: v for k, v in LEED_COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Ensure minimum required columns exist
    for col in ["source_id", "building_name_raw", "address_raw", "zip", "leed_level"]:
        if col not in df.columns:
            df[col] = ""

    # Add source tag
    df["source_name"] = "LEED"

    # Parse cert year from date string if needed
    if "leed_cert_year" in df.columns:
        df["leed_cert_year"] = pd.to_datetime(df["leed_cert_year"], errors="coerce").dt.year

    # Normalize leed_level values
    level_map = {
        "Platinum": "Platinum",
        "Gold": "Gold",
        "Silver": "Silver",
        "Certified": "Certified",
    }
    if "leed_level" in df.columns:
        df["leed_level"] = df["leed_level"].map(
            lambda x: next((v for k, v in level_map.items() if k.lower() in str(x).lower()), str(x))
        )

    # Prefix source_id
    df["source_id"] = "LEED_" + df["source_id"].astype(str)

    return df


def print_manual_instructions(config):
    """Print instructions for manual LEED data export."""
    dest = config.RAW_LEED
    print(
        f"""
╔══════════════════════════════════════════════════════════════════╗
║  MANUAL LEED EXPORT REQUIRED                                   ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Automated LEED data retrieval was not successful.               ║
║  Please export the data manually:                                ║
║                                                                  ║
║  1. Go to https://www.usgbc.org/projects                        ║
║  2. Filter:                                                      ║
║     - Location: New York, NY                                     ║
║     - Rating System: Any                                         ║
║     - Certification: Certified (all levels)                      ║
║  3. Export / download the results as CSV                         ║
║  4. Save the file to:                                            ║
║     {dest}/leed_manual_export.csv                                ║
║                                                                  ║
║  Required columns (rename if needed):                            ║
║    source_id, building_name_raw, address_raw,                    ║
║    city, zip, leed_level, leed_cert_year, project_type           ║
║                                                                  ║
║  Then re-run with: --skip-download                               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""
    )


def main():
    config = get_config()
    setup_logging()

    logger.info("=== Step 1: Get LEED data ===")

    # Check for existing manual export first
    manual_path = config.RAW_LEED / "leed_manual_export.csv"
    if manual_path.exists():
        logger.info("Found manual export at %s", manual_path)
        df = pd.read_csv(manual_path, low_memory=False)
        df = normalize_leed_df(df)
    else:
        # Try automated approaches
        df = try_api_export(config)
        if df is None:
            df = try_gbig_csv(config)

        if df is None or len(df) == 0:
            print_manual_instructions(config)
            logger.warning("No LEED data obtained. Manual export needed.")
            return

        df = normalize_leed_df(df)

    # Save cleaned output
    from leed_ll97_report.io import save_csv

    dest = config.RAW_LEED / "leed_nyc.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    save_csv(df, dest)
    logger.info("LEED ingestion complete: %d records", len(df))


if __name__ == "__main__":
    main()
