# CLAUDE.md

## Project Overview

Annual data pipeline that compares LEED-certified NYC buildings against NYC energy performance grades (Local Law 33) and Local Law 97 emissions compliance data. Produces matched datasets, summary metrics, charts, and a markdown report.

**Stack:** Python 3.11+, pandas, numpy, matplotlib, rapidfuzz, usaddress, requests, openpyxl

## Quick Reference

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# Run full pipeline
python scripts/10_run_all.py --year 2026

# Run with options
python scripts/10_run_all.py --year 2026 --skip-download
python scripts/10_run_all.py --year 2026 --use-manual-mapping
python scripts/10_run_all.py --year 2026 --min-match-confidence 70

# Lint
ruff check src/ scripts/
ruff format --check src/ scripts/

# Tests (pytest is configured but no tests exist yet)
pytest
```

## Repository Structure

```
├── src/leed_ll97_report/     # Core library package
│   ├── io.py                 # Download, CSV load/save, rate-limited HTTP
│   ├── normalize.py          # Address & field normalization (usaddress-based)
│   ├── matching.py           # 5-tier building matching engine with confidence scoring
│   ├── metrics.py            # Headline stats, grade distributions, LL97 overage
│   ├── charts.py             # matplotlib chart generation (5 chart types, 150 DPI)
│   └── report.py             # Markdown report generation from template
├── scripts/                  # Numbered pipeline steps (run sequentially)
│   ├── 00_config.py          # Central configuration (paths, URLs, thresholds)
│   ├── 01_get_leed.py        # Fetch LEED data from USGBC Elasticsearch API
│   ├── 02_get_nyc_energy_grades.py  # Download LL33 grades from NYC Open Data
│   ├── 03_get_nyc_benchmarking.py   # Download LL84 benchmarking data
│   ├── 04_get_nyc_ll97.py    # Download LL97 emissions data (.xlsx)
│   ├── 05_clean_normalize.py # Clean & normalize all datasets
│   ├── 06_match_buildings.py # Run matching engine, build master table
│   ├── 07_compute_metrics.py # Compute summary metrics
│   ├── 08_make_charts.py     # Generate PNG charts
│   ├── 09_generate_report_md.py  # Produce final markdown report
│   ├── 10_run_all.py         # End-to-end orchestrator with QA checks
│   └── scripts_helpers.py    # Shared logging & config helpers
├── report_templates/
│   └── annual_report_template.md  # Markdown template with placeholders
├── viewer/                   # Standalone HTML data explorer
│   ├── index.html            # Interactive isometric Manhattan map view
│   └── data.csv              # Pre-built viewer dataset (273 D-grade buildings)
├── notebooks/
│   └── matching_review.ipynb # Interactive matching review for ambiguous cases
├── docs/
│   ├── methodology.md        # Data sources, matching cascade, limitations
│   ├── data_dictionary.md    # Field definitions across all datasets
│   └── qa_checklist.md       # QA validation procedures
├── pyproject.toml            # Project config, dependencies, ruff settings
└── .env.example              # Environment variable template
```

## Architecture & Data Flow

```
Download (01-04) → Clean (05) → Match (06) → Metrics (07) → Charts (08) → Report (09)
```

**Data directories** (all gitignored, created at runtime):
- `data/raw/{leed,nyc_energy_grades,nyc_benchmarking,nyc_ll97}/` — timestamped downloads
- `data/cleaned/` — normalized CSVs with `_norm` suffix columns
- `data/matched/` — `master_matched_{year}.csv` and `review_queue_{year}.csv`
- `data/interim/` — optional `manual_mapping.csv` for match overrides
- `data/outputs/{year}/` — report, charts, summary CSVs, run log

## Key Conventions

### Code Style
- **Linter:** ruff with `line-length = 100`, `target-version = "py311"`
- No formatter profile is set explicitly; use `ruff format` for formatting
- Imports: standard library → third-party → local, separated by blank lines

### Configuration
- All paths, URLs, thresholds, and API settings live in `scripts/00_config.py`
- Environment variables loaded from `.env` via python-dotenv (optional overrides)
- Key thresholds: `FUZZY_ADDRESS_THRESHOLD=80`, `FUZZY_NAME_THRESHOLD=75`, `MIN_MATCH_CONFIDENCE=50`

### Normalization Pattern
Functions in `src/leed_ll97_report/normalize.py` produce `_norm` suffix columns:
- `normalize_address()` — uppercase, strip units, parse with usaddress, standardize USPS suffixes/directions
- `normalize_borough()` — maps aliases to canonical names (MANHATTAN, BROOKLYN, etc.)
- `normalize_zip()` — extract & zero-pad to 5 digits
- `normalize_bbl()` / `normalize_bin()` — pad to 10/7 digits respectively

### Matching Engine
5-tier cascade in `src/leed_ll97_report/matching.py`:
1. BBL exact match → confidence 100
2. BIN exact match → confidence 100
3. Address + ZIP exact → confidence 90
4. Address exact (no ZIP) → confidence 85-88
5. Fuzzy address (rapidfuzz `token_sort_ratio`) → confidence 70-89
6. Fuzzy name → confidence 50-69

Matches below `MIN_MATCH_CONFIDENCE` go to `review_queue_{year}.csv`. Manual overrides via `data/interim/manual_mapping.csv` (columns: `leed_source_id`, `nyc_source_id`, `decision`, `notes`).

### Raw File Naming
Downloaded files get UTC timestamp suffixes (e.g., `leed_nyc_20260215_143022.csv`). The `latest_raw_file()` function in `io.py` selects the most recent file by timestamp.

### Chart Colors
- Grades: A=`#2ecc71`, B=`#3498db`, C=`#f39c12`, D=`#e74c3c`
- LEED levels: Platinum=`#8e8e8e`, Gold=`#f1c40f`, Silver=`#bdc3c7`, Certified=`#27ae60`

## External Data Sources

| Source | API | Dataset ID |
|--------|-----|------------|
| USGBC LEED Directory | Elasticsearch (`pr-msearch.usgbc.org`) | — |
| NYC LL33 Energy Grades | NYC Open Data SODA | `355w-xvp2` |
| NYC LL84 Benchmarking | NYC Open Data SODA | `5zyy-y8am` |
| NYC LL97 Emissions | NYC Open Data (Excel) | `4hxk-b29t` |

## Viewer

The `viewer/` directory contains a self-contained HTML data explorer (`index.html` + `data.csv`). It uses PapaParse for CSV loading and renders an isometric Manhattan map view of D-grade (failing) buildings. No build step — open `index.html` directly. CSS uses custom properties for theming with a dark color scheme.

## Common Tasks

**Add a new data source:** Create `scripts/0X_get_<source>.py` following the existing pattern (download to `data/raw/<source>/` with timestamp suffix). Add cleaning logic to `05_clean_normalize.py`. Update the matching join in `matching.py:build_master_table()`.

**Adjust matching sensitivity:** Edit thresholds in `scripts/00_config.py` (`FUZZY_ADDRESS_THRESHOLD`, `FUZZY_NAME_THRESHOLD`, `MIN_MATCH_CONFIDENCE`), or pass `--min-match-confidence` to `10_run_all.py`.

**Add a new chart:** Add a function to `src/leed_ll97_report/charts.py` following the `chart_*()` pattern. Register it in `generate_all_charts()`. Update `report.py` to include it in the report template.

**Update the viewer:** Edit `viewer/index.html` directly. Regenerate `viewer/data.csv` from the master matched output if the underlying data changes.

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `REPORT_YEAR` | No (default: 2026) | Year for the annual report |
| `NYC_OPEN_DATA_APP_TOKEN` | No | Increases NYC Open Data rate limits |
| `NYC_GEOCLIENT_APP_ID` | No | NYC Geoclient API (optional geocoding) |
| `NYC_GEOCLIENT_APP_KEY` | No | NYC Geoclient API key |
