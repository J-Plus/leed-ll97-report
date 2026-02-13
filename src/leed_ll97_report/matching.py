"""
Building matching engine.

Matches LEED buildings to NYC datasets using deterministic IDs (BBL/BIN),
exact address matching, fuzzy address matching, and fuzzy name matching.
Produces confidence scores and a manual review queue.
"""

import logging

import pandas as pd
from rapidfuzz import fuzz, process

from .normalize import (
    normalize_address,
    normalize_bbl,
    normalize_bin,
    normalize_borough,
    normalize_building_name,
    normalize_zip,
)

logger = logging.getLogger(__name__)


def match_buildings(
    leed_df: pd.DataFrame,
    nyc_df: pd.DataFrame,
    fuzzy_address_threshold: int = 80,
    fuzzy_name_threshold: int = 75,
    min_confidence: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Match LEED buildings to NYC building records.

    Returns:
        matched_df: DataFrame of all matches with confidence scores
        review_queue: DataFrame of ambiguous matches below min_confidence
    """
    logger.info(
        "Matching %d LEED records against %d NYC records",
        len(leed_df),
        len(nyc_df),
    )

    matches = []
    unmatched_leed = []

    def _clean(val) -> str:
        """Convert to string, stripping NaN/None to empty."""
        s = str(val).strip() if val is not None else ""
        return "" if s.lower() in ("nan", "none", "") else s

    # Build lookup indexes on NYC side
    nyc_by_bbl = {}
    nyc_by_bin = {}
    nyc_by_addr_zip = {}
    nyc_addr_list = []

    for idx, row in nyc_df.iterrows():
        bbl = _clean(row.get("bbl_norm", ""))
        bin_ = _clean(row.get("bin_norm", ""))
        addr = _clean(row.get("address_norm", ""))
        zip_ = _clean(row.get("zip_norm", ""))
        name = _clean(row.get("building_name_norm", ""))

        if bbl:
            nyc_by_bbl.setdefault(bbl, []).append(idx)
        if bin_:
            nyc_by_bin.setdefault(bin_, []).append(idx)
        if addr and zip_:
            key = f"{addr}|{zip_}"
            nyc_by_addr_zip.setdefault(key, []).append(idx)

        if addr:
            nyc_addr_list.append((idx, addr, zip_, name))

    # Pre-compute address and name strings for fuzzy matching
    nyc_addresses = {idx: addr for idx, addr, zip_, name in nyc_addr_list}
    nyc_names = {idx: name for idx, addr, zip_, name in nyc_addr_list if name}
    nyc_zips = {idx: zip_ for idx, addr, zip_, name in nyc_addr_list}

    for _, leed_row in leed_df.iterrows():
        leed_id = leed_row.get("source_id", "")
        leed_bbl = _clean(leed_row.get("bbl_norm", ""))
        leed_bin = _clean(leed_row.get("bin_norm", ""))
        leed_addr = _clean(leed_row.get("address_norm", ""))
        leed_zip = _clean(leed_row.get("zip_norm", ""))
        leed_name = _clean(leed_row.get("building_name_norm", ""))
        leed_borough = _clean(leed_row.get("borough_norm", ""))

        best_match = None
        best_confidence = 0
        best_method = ""
        best_notes = ""

        # Strategy 1: BBL match
        if leed_bbl and leed_bbl in nyc_by_bbl:
            nyc_idx = nyc_by_bbl[leed_bbl][0]
            best_match = nyc_idx
            best_confidence = 100
            best_method = "exact_bbl"
            best_notes = f"BBL={leed_bbl}"

        # Strategy 2: BIN match
        if best_confidence < 100 and leed_bin and leed_bin in nyc_by_bin:
            nyc_idx = nyc_by_bin[leed_bin][0]
            if best_confidence < 100:
                best_match = nyc_idx
                best_confidence = 100
                best_method = "exact_bin"
                best_notes = f"BIN={leed_bin}"

        # Strategy 3: Exact address + zip match
        if best_confidence < 95 and leed_addr and leed_zip:
            key = f"{leed_addr}|{leed_zip}"
            if key in nyc_by_addr_zip:
                nyc_idx = nyc_by_addr_zip[key][0]
                best_match = nyc_idx
                best_confidence = 90
                best_method = "exact_address"
                best_notes = f"addr={leed_addr}, zip={leed_zip}"

        # Strategy 3b: Exact address match (no zip required)
        if best_confidence < 90 and leed_addr:
            for idx, addr in nyc_addresses.items():
                if addr == leed_addr:
                    # Check borough match for extra confidence
                    nyc_boro = _clean(nyc_df.loc[idx].get("borough_norm", ""))
                    if leed_borough and nyc_boro and leed_borough == nyc_boro:
                        best_match = idx
                        best_confidence = 88
                        best_method = "exact_address_borough"
                        best_notes = f"addr={leed_addr}, borough={leed_borough}"
                        break
                    elif not best_match or best_confidence < 85:
                        best_match = idx
                        best_confidence = 85
                        best_method = "exact_address_no_zip"
                        best_notes = f"addr={leed_addr}"

        # Strategy 4: Fuzzy address match (within same zip or borough)
        if best_confidence < 80 and leed_addr:
            candidates = {}
            for idx, addr in nyc_addresses.items():
                nyc_zip = nyc_zips.get(idx, "")
                # Match within same zip if both have zip
                if leed_zip and nyc_zip and leed_zip == nyc_zip:
                    candidates[idx] = addr
                # Or same borough if zip not available
                elif leed_borough:
                    nyc_boro = _clean(nyc_df.loc[idx].get("borough_norm", ""))
                    if nyc_boro == leed_borough:
                        candidates[idx] = addr
            if candidates:
                result = process.extractOne(
                    leed_addr,
                    candidates,
                    scorer=fuzz.token_sort_ratio,
                    score_cutoff=fuzzy_address_threshold,
                )
                if result:
                    match_str, score, nyc_idx = result
                    confidence = int(70 + (score - fuzzy_address_threshold) * 19 / (100 - fuzzy_address_threshold))
                    confidence = min(89, max(70, confidence))
                    if confidence > best_confidence:
                        best_match = nyc_idx
                        best_confidence = confidence
                        best_method = "fuzzy_address"
                        best_notes = f"score={score:.0f}, addr={match_str}"

        # Strategy 5: Fuzzy name match (within same zip or borough)
        if best_confidence < 70 and leed_name:
            candidates = {}
            for idx, name in nyc_names.items():
                if not name:
                    continue
                same_zip = nyc_zips.get(idx) == leed_zip if leed_zip else False
                same_borough = str(nyc_df.loc[idx].get("borough_norm", "")) == leed_borough if leed_borough else False
                if same_zip or same_borough:
                    candidates[idx] = name

            if candidates:
                result = process.extractOne(
                    leed_name,
                    candidates,
                    scorer=fuzz.token_sort_ratio,
                    score_cutoff=fuzzy_name_threshold,
                )
                if result:
                    match_str, score, nyc_idx = result
                    confidence = int(50 + (score - fuzzy_name_threshold) * 19 / (100 - fuzzy_name_threshold))
                    confidence = min(69, max(50, confidence))
                    if confidence > best_confidence:
                        best_match = nyc_idx
                        best_confidence = confidence
                        best_method = "fuzzy_name"
                        best_notes = f"score={score:.0f}, name={match_str}"

        if best_match is not None:
            matches.append({
                "leed_source_id": leed_id,
                "nyc_index": best_match,
                "match_confidence": best_confidence,
                "match_method": best_method,
                "match_notes": best_notes,
            })
        else:
            unmatched_leed.append({
                "leed_source_id": leed_id,
                "building_name_raw": leed_row.get("building_name_raw", ""),
                "address_raw": leed_row.get("address_raw", ""),
                "zip": leed_row.get("zip", ""),
                "match_confidence": 0,
                "match_method": "none",
                "match_notes": "No match found",
            })

    matched_df = pd.DataFrame(matches)
    unmatched_df = pd.DataFrame(unmatched_leed)

    # Build review queue: low-confidence matches + unmatched
    review_queue = pd.concat([
        matched_df[matched_df["match_confidence"] < min_confidence],
        unmatched_df,
    ], ignore_index=True)

    logger.info(
        "Matching complete: %d matched, %d unmatched, %d in review queue",
        len(matched_df),
        len(unmatched_df),
        len(review_queue),
    )

    return matched_df, review_queue


def apply_manual_mapping(
    matched_df: pd.DataFrame,
    manual_mapping_path: str | None,
) -> pd.DataFrame:
    """
    Override matches with manual mapping decisions.

    Manual mapping CSV columns:
        leed_source_id, nyc_source_id, decision, notes
    Decisions: 'match', 'reject', 'skip'
    """
    if not manual_mapping_path:
        return matched_df

    try:
        manual = pd.read_csv(manual_mapping_path)
    except FileNotFoundError:
        logger.info("No manual mapping file found at %s", manual_mapping_path)
        return matched_df

    logger.info("Applying %d manual mapping decisions", len(manual))

    for _, row in manual.iterrows():
        leed_id = row["leed_source_id"]
        decision = row.get("decision", "match")

        if decision == "reject":
            matched_df = matched_df[matched_df["leed_source_id"] != leed_id]
        elif decision == "match":
            # Update or add the match
            mask = matched_df["leed_source_id"] == leed_id
            if mask.any():
                matched_df.loc[mask, "nyc_source_id"] = row["nyc_source_id"]
                matched_df.loc[mask, "match_confidence"] = 100
                matched_df.loc[mask, "match_method"] = "manual_review"
                matched_df.loc[mask, "match_notes"] = row.get("notes", "manual override")
            else:
                matched_df = pd.concat([matched_df, pd.DataFrame([{
                    "leed_source_id": leed_id,
                    "nyc_source_id": row["nyc_source_id"],
                    "match_confidence": 100,
                    "match_method": "manual_review",
                    "match_notes": row.get("notes", "manual override"),
                }])], ignore_index=True)

    return matched_df


def build_master_table(
    leed_df: pd.DataFrame,
    nyc_grades_df: pd.DataFrame,
    nyc_bench_df: pd.DataFrame,
    nyc_ll97_df: pd.DataFrame,
    matched_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join matched records into a single master table with all fields
    from the data contract. One row per LEED match.
    """
    if matched_df.empty:
        return pd.DataFrame()

    # Start from matched records (one row per LEED building)
    master = matched_df.copy()

    # Add LEED fields via source_id lookup
    leed_indexed = leed_df.set_index("source_id", drop=False)
    for col in ["building_name_raw", "address_raw", "address_norm", "zip",
                "leed_level", "leed_cert_year", "city", "source_name",
                "lat", "lon", "project_type", "leed_version", "gross_sqft"]:
        if col in leed_indexed.columns:
            master[col] = master["leed_source_id"].map(leed_indexed[col])

    # Add NYC grades fields via nyc_index lookup
    if "nyc_index" in master.columns and not nyc_grades_df.empty:
        nyc_idx = master["nyc_index"]
        for src_col, dest_col in [
            ("energy_grade", "energy_grade"),
            ("energy_star_score", "energy_star_score"),
            ("site_eui", "site_eui"),
            ("bbl", "bbl"),
            ("bbl_norm", "bbl_norm"),
            ("borough_norm", "borough"),
            ("address_raw", "nyc_address"),
            ("source_id", "nyc_grades_source_id"),
        ]:
            if src_col in nyc_grades_df.columns:
                master[dest_col] = nyc_idx.map(
                    lambda i, c=src_col: nyc_grades_df.at[i, c] if i in nyc_grades_df.index else None
                )

    # Add LL97 fields via BBL join (deduplicate LL97 first)
    if not nyc_ll97_df.empty and "bbl" in master.columns:
        ll97_cols = ["bbl", "ghg_emissions_tco2e", "ll97_limit_tco2e", "ll97_overage_tco2e"]
        available = [c for c in ll97_cols if c in nyc_ll97_df.columns]
        if "bbl" in available:
            ll97_dedup = nyc_ll97_df[available].drop_duplicates(subset=["bbl"])
            ll97_lookup = ll97_dedup.set_index("bbl")
            master_bbl = master["bbl"].astype(str).replace({"nan": "", "None": ""})
            for col in [c for c in available if c != "bbl"]:
                if col in ll97_lookup.columns:
                    master[col] = master_bbl.map(ll97_lookup[col])

    # Add benchmarking GHG if not already present from LL97
    if not nyc_bench_df.empty and "bbl" in master.columns:
        bench_ghg_cols = ["bbl", "ghg_emissions_tco2e", "site_eui"]
        avail = [c for c in bench_ghg_cols if c in nyc_bench_df.columns]
        if "bbl" in avail and len(avail) > 1:
            bench_dedup = nyc_bench_df[avail].drop_duplicates(subset=["bbl"])
            bench_lookup = bench_dedup.set_index("bbl")
            master_bbl = master["bbl"].astype(str).replace({"nan": "", "None": ""})
            for col in [c for c in avail if c != "bbl"]:
                if col not in master.columns or master[col].isna().all():
                    if col in bench_lookup.columns:
                        master[col] = master_bbl.map(bench_lookup[col])

    # Ensure all data contract columns exist
    contract_cols = [
        "source_id", "source_name", "building_name_raw", "address_raw",
        "address_norm", "bbl", "bin", "borough", "zip",
        "leed_level", "leed_cert_year", "energy_grade", "energy_star_score",
        "site_eui", "ghg_emissions_tco2e", "ll97_limit_tco2e",
        "ll97_overage_tco2e", "match_confidence", "match_method", "match_notes",
    ]
    for col in contract_cols:
        if col not in master.columns:
            master[col] = None

    # Use leed source_id as the primary source_id
    master["source_id"] = master["leed_source_id"]

    return master
