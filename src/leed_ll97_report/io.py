"""
I/O helpers: download files, load/save CSVs with timestamps.
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)


def download_csv(url: str, dest_dir: Path, filename: str, app_token: str = "") -> Path:
    """Download a CSV from a URL and save with a timestamp suffix."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = Path(filename).stem
    dest = dest_dir / f"{stem}_{ts}.csv"

    headers = {}
    if app_token:
        headers["X-App-Token"] = app_token

    logger.info("Downloading %s → %s", url, dest)
    resp = requests.get(url, headers=headers, timeout=300)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    logger.info("Saved %d bytes to %s", len(resp.content), dest)
    return dest


def latest_raw_file(raw_dir: Path, prefix: str) -> Path | None:
    """Return the most recently downloaded file matching a prefix."""
    candidates = sorted(raw_dir.glob(f"{prefix}_*.csv"), reverse=True)
    return candidates[0] if candidates else None


def load_csv(path: Path, **kwargs) -> pd.DataFrame:
    """Load a CSV into a DataFrame with logging."""
    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False, **kwargs)
    logger.info("Loaded %d rows × %d cols from %s", len(df), len(df.columns), path.name)
    return df


def save_csv(df: pd.DataFrame, path: Path) -> Path:
    """Save a DataFrame to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info("Saved %d rows to %s", len(df), path)
    return path


def throttled_get(url: str, params: dict | None = None, delay: float = 1.0, **kwargs) -> requests.Response:
    """GET with a polite delay for scraping."""
    time.sleep(delay)
    resp = requests.get(url, params=params, timeout=60, **kwargs)
    resp.raise_for_status()
    return resp
