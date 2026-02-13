# QA Checklist

Run through this checklist after each pipeline execution.

## Data Ingestion
- [ ] LEED CSV loaded with expected record count (compare to prior year)
- [ ] NYC Energy Grades CSV downloaded successfully
- [ ] NYC Benchmarking CSV downloaded successfully
- [ ] NYC LL97 CSV downloaded successfully
- [ ] Download timestamps recorded in run log

## Cleaning & Normalization
- [ ] All cleaned CSVs saved to `data/cleaned/`
- [ ] Address normalization applied (spot-check 10 records)
- [ ] ZIP codes are 5 digits
- [ ] BBL values are 10 digits where present
- [ ] BIN values are 7 digits where present
- [ ] Borough values are standardized (MANHATTAN, BROOKLYN, BRONX, QUEENS, STATEN ISLAND)
- [ ] No unexpected null spikes vs prior year

## Matching
- [ ] Match rate within expected range (compare to prior year if available)
- [ ] No single NYC building matched to multiple LEED records (unless flagged)
- [ ] Confidence distribution looks reasonable
- [ ] Review queue generated for low-confidence matches
- [ ] Manual mapping applied if `--use-manual-mapping` was set

## Metrics
- [ ] Energy grades only contain A, B, C, D values
- [ ] Headline stats look reasonable
- [ ] LL97 overage calculation is correct (emissions − limit)
- [ ] No negative building counts

## Charts
- [ ] All 5 expected charts generated as PNGs
- [ ] Charts are readable with correct labels
- [ ] No blank or error charts

## Report
- [ ] Markdown report generated
- [ ] Headline table populated
- [ ] Chart images referenced correctly
- [ ] Methodology summary present

## Outlier Checks
- [ ] Site EUI values: no extreme outliers (> 1000 kBtu/sq ft)
- [ ] GHG emissions: no unreasonable values
- [ ] Certification years are within valid range (2000–current year)
- [ ] ENERGY STAR scores are 1–100

## Reproducibility
- [ ] Run log includes git commit hash
- [ ] Run log includes Python version
- [ ] Run log includes dataset download timestamps
- [ ] Run log includes record counts at each stage
- [ ] Dependencies pinned in pyproject.toml
