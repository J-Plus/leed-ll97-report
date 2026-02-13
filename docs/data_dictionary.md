# Data Dictionary

## Master Matched Table

`data/matched/master_matched_{year}.csv`

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | string | Unique identifier from the LEED source (prefixed `LEED_`) |
| `source_name` | string | Source dataset name (`LEED`) |
| `building_name_raw` | string | Original building name from LEED |
| `address_raw` | string | Original street address from LEED |
| `address_norm` | string | Normalized address used for matching |
| `bbl` | string | NYC Borough-Block-Lot (10 digits) |
| `bin` | string | NYC Building Identification Number (7 digits) |
| `borough` | string | NYC borough (MANHATTAN, BROOKLYN, BRONX, QUEENS, STATEN ISLAND) |
| `zip` | string | 5-digit ZIP code |
| `leed_level` | string | Certification level: Platinum, Gold, Silver, Certified |
| `leed_cert_year` | integer | Year of LEED certification |
| `energy_grade` | string | NYC energy letter grade: A, B, C, D |
| `energy_star_score` | float | ENERGY STAR score (1–100) |
| `site_eui` | float | Site Energy Use Intensity (kBtu/sq ft) |
| `ghg_emissions_tco2e` | float | Total GHG emissions (metric tons CO2e) |
| `ll97_limit_tco2e` | float | LL97 emissions limit (metric tons CO2e) |
| `ll97_overage_tco2e` | float | Emissions above limit (negative = compliant) |
| `match_confidence` | integer | Match confidence score (0–100) |
| `match_method` | string | Match method used (see below) |
| `match_notes` | string | Details about the match (score, matched value) |

## Match Methods

| Method | Description | Confidence Range |
|--------|-------------|------------------|
| `exact_bbl` | Matched on Borough-Block-Lot | 100 |
| `exact_bin` | Matched on Building Identification Number | 100 |
| `exact_address` | Exact normalized address + ZIP | 90 |
| `fuzzy_address` | Fuzzy address match (token sort ratio) | 70–89 |
| `fuzzy_name` | Fuzzy building name match within same ZIP/borough | 50–69 |
| `manual_review` | Manually confirmed match | 100 |
| `none` | No match found | 0 |

## Review Queue

`data/matched/review_queue_{year}.csv`

| Field | Type | Description |
|-------|------|-------------|
| `leed_source_id` | string | LEED building identifier |
| `building_name_raw` | string | LEED building name |
| `address_raw` | string | LEED address |
| `zip` | string | ZIP code |
| `match_confidence` | integer | Confidence score (0 or below threshold) |
| `match_method` | string | Best attempted method |
| `match_notes` | string | Reason for review queue placement |

## Manual Mapping

`data/interim/manual_mapping.csv`

| Field | Type | Description |
|-------|------|-------------|
| `leed_source_id` | string | LEED building identifier |
| `nyc_source_id` | string | NYC building identifier to link to |
| `decision` | string | `match`, `reject`, or `skip` |
| `notes` | string | Reviewer notes |

## Summary Tables

| File | Description |
|------|-------------|
| `headline_{year}.csv` | Single-row headline statistics |
| `leed_by_grade_{year}.csv` | Count of LEED buildings by energy grade |
| `leed_level_by_grade_{year}.csv` | Cross-tab of LEED level × energy grade |
| `ll97_overage_summary_{year}.csv` | LL97 overage statistics |
| `match_coverage_stats_{year}.csv` | Match method and confidence breakdown |
