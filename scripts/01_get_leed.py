#!/usr/bin/env python3
"""
Fetch LEED-certified NYC buildings from the USGBC project directory.

Uses the public Elasticsearch endpoint backing usgbc.org/projects.
Falls back to manual export if the endpoint is unavailable.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from scripts_helpers import setup_logging, get_config

logger = logging.getLogger(__name__)

# ── Elasticsearch query for certified NYC buildings ────────────────────────
def _build_es_query(from_: int = 0, size: int = 2000) -> dict:
    return {
        "query": {
            "bool": {
                "must": [
                    {"match": {"published_status": "1"}},
                    {"match": {"is_certified": "Yes"}},
                    {"terms": {"state_name.raw": ["New York"]}},
                    {"terms": {"city.raw": ["New York"]}},
                ],
                "must_not": [
                    {"terms": {"confidential.raw": ["1", "this is confidential"]}},
                    {"match": {"status": "Denied"}},
                ],
            }
        },
        "_source": {"includes": ["*"], "excludes": []},
        "from": from_,
        "size": size,
        "sort": [{"certification_date": {"order": "desc"}}],
        "track_total_hits": True,
    }


def _flatten_es_hit(hit: dict) -> dict:
    """Flatten an ES _source dict where values are single-element lists."""
    src = hit.get("_source", {})
    flat = {}
    for k, v in src.items():
        if isinstance(v, list) and len(v) == 1:
            flat[k] = v[0]
        elif isinstance(v, list) and len(v) == 0:
            flat[k] = None
        else:
            flat[k] = v
    return flat


def fetch_from_elasticsearch(config) -> pd.DataFrame | None:
    """Fetch all certified NYC LEED buildings from USGBC Elasticsearch."""
    url = config.LEED_ES_URL
    page_size = config.LEED_ES_PAGE_SIZE
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.usgbc.org",
        "Referer": "https://www.usgbc.org/projects",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    all_records = []
    from_ = 0

    while True:
        query = _build_es_query(from_=from_, size=page_size)
        logger.info("LEED ES request: from=%d, size=%d", from_, page_size)

        try:
            resp = requests.post(url, json=query, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            logger.warning("LEED ES request failed: %s", exc)
            return None

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {}).get("value", 0)

        if not hits:
            break

        records = [_flatten_es_hit(h) for h in hits]
        all_records.extend(records)
        logger.info("  fetched %d records (total so far: %d / %d)", len(hits), len(all_records), total)

        if len(all_records) >= total or len(hits) < page_size:
            break
        from_ += page_size

    if not all_records:
        return None

    return pd.DataFrame(all_records)


def normalize_leed_df(df: pd.DataFrame) -> pd.DataFrame:
    """Map USGBC Elasticsearch fields to our standard schema."""
    col_map = {
        "prjt_id": "source_id",
        "title": "building_name_raw",
        "address_line1": "address_raw",
        "city": "city",
        "state": "state",
        "postal_code": "zip",
        "certification_level": "leed_level",
        "certification_date": "leed_cert_date_epoch",
        "rating_system": "project_type",
        "rating_system_version": "leed_version",
        "prjt_site_size": "gross_sqft",
        "geo_lat": "lat",
        "geo_lng": "lon",
    }
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Parse certification date from epoch seconds
    if "leed_cert_date_epoch" in df.columns:
        df["leed_cert_date_epoch"] = pd.to_numeric(df["leed_cert_date_epoch"], errors="coerce")
        df["leed_cert_year"] = pd.to_datetime(
            df["leed_cert_date_epoch"], unit="s", errors="coerce"
        ).dt.year

    # Ensure standard columns
    for col in ["source_id", "building_name_raw", "address_raw", "zip", "leed_level"]:
        if col not in df.columns:
            df[col] = ""

    df["source_name"] = "LEED"
    df["source_id"] = "LEED_" + df["source_id"].astype(str)

    # Normalize level values
    level_map = {"Platinum": "Platinum", "Gold": "Gold", "Silver": "Silver", "Certified": "Certified"}
    if "leed_level" in df.columns:
        df["leed_level"] = df["leed_level"].map(
            lambda x: next((v for k, v in level_map.items() if k.lower() in str(x).lower()), str(x))
        )

    return df


def print_manual_instructions(config):
    """Print instructions for manual LEED data export."""
    dest = config.RAW_LEED
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  MANUAL LEED EXPORT REQUIRED                                   ║
╠══════════════════════════════════════════════════════════════════╣
║  Automated retrieval from USGBC failed.                         ║
║                                                                  ║
║  1. Go to https://www.usgbc.org/projects                        ║
║  2. Filter: State=New York, City=New York, Certified             ║
║  3. Manually compile results into a CSV                          ║
║  4. Save to: {dest}/leed_manual_export.csv          ║
║  5. Re-run with: --skip-download                                 ║
╚══════════════════════════════════════════════════════════════════╝
""")


def main():
    config = get_config()
    setup_logging()

    logger.info("=== Step 1: Get LEED data ===")

    from leed_ll97_report.io import save_csv

    # Check for manual export first
    manual_path = config.RAW_LEED / "leed_manual_export.csv"
    if manual_path.exists():
        logger.info("Found manual export at %s", manual_path)
        df = pd.read_csv(manual_path, low_memory=False)
        df = normalize_leed_df(df)
    else:
        # Fetch from Elasticsearch
        df = fetch_from_elasticsearch(config)

        if df is None or len(df) == 0:
            print_manual_instructions(config)
            logger.warning("No LEED data obtained.")
            return

        df = normalize_leed_df(df)

    # Save
    config.RAW_LEED.mkdir(parents=True, exist_ok=True)
    save_csv(df, config.RAW_LEED / "leed_nyc.csv")
    logger.info("LEED ingestion complete: %d records", len(df))


if __name__ == "__main__":
    main()
