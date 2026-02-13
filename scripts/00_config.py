"""
Central configuration for the LEED vs NYC pipeline.
All paths, URLs, and parameters live here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
CLEANED_DIR = DATA_DIR / "cleaned"
MATCHED_DIR = DATA_DIR / "matched"
OUTPUTS_DIR = DATA_DIR / "outputs"

RAW_LEED = RAW_DIR / "leed"
RAW_ENERGY_GRADES = RAW_DIR / "nyc_energy_grades"
RAW_BENCHMARKING = RAW_DIR / "nyc_benchmarking"
RAW_LL97 = RAW_DIR / "nyc_ll97"

REPORT_TEMPLATES_DIR = ROOT_DIR / "report_templates"
MANUAL_MAPPING_PATH = INTERIM_DIR / "manual_mapping.csv"

# ── Report year ────────────────────────────────────────────────────────────
REPORT_YEAR = int(os.getenv("REPORT_YEAR", "2026"))

# ── NYC Open Data endpoints (Socrata SODA API, CSV export) ─────────────────
# Energy grades – LL33 letter grades (DOB Sustainability Compliance Map: LL33)
# Dataset ID: 355w-xvp2
NYC_ENERGY_GRADES_URL = (
    "https://data.cityofnewyork.us/api/views/355w-xvp2/rows.csv?accessType=DOWNLOAD"
)

# Benchmarking – LL84 covered buildings energy/water use
# Dataset ID: 5zyy-y8am (CY2022+; for older years use 7x5e-2fxh)
NYC_BENCHMARKING_URL = (
    "https://data.cityofnewyork.us/api/views/5zyy-y8am/rows.csv?accessType=DOWNLOAD"
)

# LL97 – Covered buildings with emissions limits
# This is an Excel attachment from the DOB Sustainability Compliance Map (4hxk-b29t)
# The pipeline downloads the .xlsx and converts it
NYC_LL97_URL = (
    "https://data.cityofnewyork.us/api/views/4hxk-b29t/files/"
    "f2d894eb-9b7d-45d6-875f-0642c0ba7610?download=true&filename=LL97.xlsx"
)

NYC_OPEN_DATA_APP_TOKEN = os.getenv("NYC_OPEN_DATA_APP_TOKEN", "")

# ── LEED ───────────────────────────────────────────────────────────────────
# USGBC Project Directory – public Elasticsearch backend
LEED_ES_URL = (
    "https://pr-msearch.usgbc.org/"
    "elasticsearch_index_live_usgbc_projects_dev/_search"
)
LEED_ES_PAGE_SIZE = 2000  # max results per request (ES default limit ~10k)

# ── Matching parameters ────────────────────────────────────────────────────
FUZZY_ADDRESS_THRESHOLD = 80   # rapidfuzz score for address matching
FUZZY_NAME_THRESHOLD = 75      # rapidfuzz score for name matching
MIN_MATCH_CONFIDENCE = 50      # below this → manual review queue

# ── Geocoding (optional) ──────────────────────────────────────────────────
NYC_GEOCLIENT_APP_ID = os.getenv("NYC_GEOCLIENT_APP_ID", "")
NYC_GEOCLIENT_APP_KEY = os.getenv("NYC_GEOCLIENT_APP_KEY", "")
GEOCODE_DISTANCE_THRESHOLD_M = 50  # meters

# ── Logging ────────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
