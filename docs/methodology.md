# Methodology

## Data Sources

### LEED Project Directory
- Source: USGBC (U.S. Green Building Council)
- Scope: All LEED-certified buildings in New York City
- Fields: Building name, address, certification level (Platinum/Gold/Silver/Certified), certification year, project type

### NYC Energy Grades (Local Law 33)
- Source: NYC Open Data
- Scope: Covered buildings required to display energy efficiency letter grades (A–D)
- Grade is derived from ENERGY STAR score: A (≥85), B (70–84), C (55–69), D (<55)

### NYC Benchmarking (Local Law 84)
- Source: NYC Open Data
- Scope: Buildings over 25,000 sq ft required to report energy and water use annually
- Key fields: Site EUI, ENERGY STAR score, GHG emissions

### NYC LL97 Emissions
- Source: NYC Open Data
- Scope: Buildings covered by Local Law 97 with emissions limits
- Key fields: Actual emissions (tCO2e), emissions limit, building class

## Building Matching

Buildings are matched between LEED and NYC datasets using a priority cascade:

1. **BBL/BIN match** (confidence: 100): Deterministic join on NYC Borough-Block-Lot or Building Identification Number
2. **Exact address + ZIP** (confidence: 90): Normalized address string equality within same ZIP code
3. **Fuzzy address** (confidence: 70–89): RapidFuzz token sort ratio on normalized addresses, minimum threshold 80
4. **Fuzzy building name** (confidence: 50–69): RapidFuzz token sort ratio on building names within same ZIP or borough, minimum threshold 75
5. **Unmatched** (confidence: 0): Placed in manual review queue

### Address Normalization
- Uppercase conversion
- Punctuation removal
- Unit/suite/floor removal
- Ordinal normalization (42ND → 42)
- USPS standard suffix mapping (STREET → ST, AVENUE → AVE)
- Directional standardization (NORTH → N)
- Parsed with `usaddress` library

### Confidence Scoring
- 100: Deterministic ID match (BBL or BIN)
- 90: Exact normalized address + ZIP
- 70–89: Fuzzy address match (scaled by match score)
- 50–69: Fuzzy name match (scaled by match score)
- <50: Flagged for manual review

## Metrics Computation

### Headline Stats
- Total LEED buildings analyzed
- Match rate (% with NYC grade)
- % of matched LEED buildings with grade C or D
- % above LL97 emissions limit

### LL97 Analysis
- Overage = actual emissions − emissions limit
- Buildings with overage > 0 are above the LL97 cap

### Degradation Analysis
- Certification age = report year − LEED certification year
- Pearson correlation between certification age and numeric grade (A=4, B=3, C=2, D=1)
- Negative correlation suggests older certifications perform worse

## Limitations
- LEED data coverage depends on USGBC export availability
- Some small LEED buildings may be below NYC reporting thresholds
- Energy grades are annual snapshots; LEED certification is point-in-time
- LL97 limits change across compliance periods (2024–2029 vs 2030+)
- Fuzzy matching may produce false positives or miss valid matches
