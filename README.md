# LEED vs NYC Energy Grades & LL97 Annual Report

A repeatable annual pipeline that compares LEED-certified NYC buildings against NYC energy performance grades and Local Law 97 emissions data.

## Quickstart

```bash
# 1. Clone and install
cd leed-ll97-report
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Copy environment config
cp .env.example .env
# Edit .env if you have an NYC Open Data app token (optional)

# 3. Run the full pipeline for 2026
python scripts/10_run_all.py --year 2026

# 4. Check outputs
ls data/outputs/2026/
```

## Pipeline Steps

| Step | Script | Description |
|------|--------|-------------|
| 01 | `01_get_leed.py` | Fetch LEED-certified NYC buildings |
| 02 | `02_get_nyc_energy_grades.py` | Download NYC LL33 energy letter grades |
| 03 | `03_get_nyc_benchmarking.py` | Download NYC LL84 benchmarking data |
| 04 | `04_get_nyc_ll97.py` | Download NYC LL97 emissions data |
| 05 | `05_clean_normalize.py` | Clean and normalize all datasets |
| 06 | `06_match_buildings.py` | Match buildings across datasets |
| 07 | `07_compute_metrics.py` | Compute summary statistics |
| 08 | `08_make_charts.py` | Generate PNG charts |
| 09 | `09_generate_report_md.py` | Generate markdown report |
| 10 | `10_run_all.py` | Run all steps end-to-end |

## Run Options

```bash
# Skip re-downloading data
python scripts/10_run_all.py --year 2026 --skip-download

# Apply manual mapping overrides
python scripts/10_run_all.py --year 2026 --use-manual-mapping

# Set minimum match confidence
python scripts/10_run_all.py --year 2026 --min-match-confidence 70
```

## LEED Data

If automated LEED retrieval fails, the pipeline prints manual export instructions. Place a manually exported CSV at `data/raw/leed/leed_manual_export.csv` and re-run with `--skip-download`.

## Manual Review Workflow

1. After matching, review `data/matched/review_queue_{year}.csv`
2. Create `data/interim/manual_mapping.csv` with columns:
   - `leed_source_id`, `nyc_source_id`, `decision` (match/reject/skip), `notes`
3. Re-run with `--use-manual-mapping`

## Outputs

All outputs go to `data/outputs/{year}/`:

- `annual_report_{year}.md` — full markdown report
- `master_matched_{year}.csv` — joined master table
- Summary CSVs (grade distributions, LL97 overage, match stats)
- PNG charts (grade distribution, LL97 histogram, degradation, match quality)
- `run_log.txt` — pipeline execution log

## Documentation

- [Methodology](docs/methodology.md)
- [Data Dictionary](docs/data_dictionary.md)
- [QA Checklist](docs/qa_checklist.md)
