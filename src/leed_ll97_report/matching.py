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

    # Build lookup indexes on NYC side
    nyc_by_bbl = {}
    nyc_by_bin = {}
    nyc_by_addr_zip = {}
    nyc_addr_list = []

    for idx, row in nyc_df.iterrows():
        bbl = str(row.get("bbl_norm", "")).strip()
        bin_ = str(row.get("bin_norm", "")).strip()
        addr = str(row.get("address_norm", "")).strip()
        zip_ = str(row.get("zip_norm", "")).strip()
        name = str(row.get("building_name_norm", "")).strip()

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
        leed_bbl = str(leed_row.get("bbl_norm", "")).strip()
        leed_bin = str(leed_row.get("bin_norm", "")).strip()
        leed_addr = str(leed_row.get("address_norm", "")).strip()
        leed_zip = str(leed_row.get("zip_norm", "")).strip()
        leed_name = str(leed_row.get("building_name_norm", "")).strip()
        leed_borough = str(leed_row.get("borough_norm", "")).strip()

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

        # Strategy 4: Fuzzy address match (within same zip)
        if best_confidence < 80 and leed_addr:
            candidates = {
                idx: addr
                for idx, addr in nyc_addresses.items()
                if nyc_zips.get(idx) == leed_zip or not leed_zip
            }
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
    from the data contract.
    """
    # Merge LEED data with match info
    master = matched_df.merge(
        leed_df,
        left_on="leed_source_id",
        right_on="source_id",
        how="left",
        suffixes=("", "_leed"),
    )

    # Merge NYC grades (use nyc_index to join)
    if "nyc_index" in master.columns and not nyc_grades_df.empty:
        grades_cols = ["source_id", "energy_grade", "energy_star_score",
                       "site_eui", "building_name_raw", "address_raw",
                       "bbl", "bin", "borough", "zip"]
        available_cols = [c for c in grades_cols if c in nyc_grades_df.columns]
        grade_subset = nyc_grades_df[available_cols].copy()
        grade_subset = grade_subset.rename(columns={
            "source_id": "nyc_grades_source_id",
            "building_name_raw": "nyc_building_name",
            "address_raw": "nyc_address",
        })

        # Use index-based join for matched records
        master["_nyc_idx"] = master["nyc_index"]
        nyc_indexed = grade_subset.copy()
        nyc_indexed["_nyc_idx"] = nyc_indexed.index

        master = master.merge(nyc_indexed, on="_nyc_idx", how="left", suffixes=("", "_nyc"))
        master = master.drop(columns=["_nyc_idx"], errors="ignore")

    # Merge LL97 data if available
    if not nyc_ll97_df.empty:
        ll97_cols = ["bbl", "ghg_emissions_tco2e", "ll97_limit_tco2e", "ll97_overage_tco2e"]
        available_ll97 = [c for c in ll97_cols if c in nyc_ll97_df.columns]
        if "bbl" in available_ll97 and "bbl" in master.columns:
            ll97_subset = nyc_ll97_df[available_ll97].copy()
            ll97_subset = ll97_subset.rename(columns={"bbl": "bbl_ll97"})
            # Try BBL join
            master = master.merge(
                ll97_subset,
                left_on="bbl",
                right_on="bbl_ll97",
                how="left",
                suffixes=("", "_ll97"),
            )

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

    return master
