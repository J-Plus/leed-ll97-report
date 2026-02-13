#!/usr/bin/env python3
"""
Clean and normalize all raw datasets into a standard schema.

Reads the latest raw files, normalizes addresses/names/IDs,
and saves cleaned CSVs to data/cleaned/.
"""

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts_helpers import setup_logging, get_config

logger = logging.getLogger(__name__)


def clean_leed(config) -> pd.DataFrame:
    """Clean and normalize LEED data."""
    from leed_ll97_report.io import load_csv, latest_raw_file
    from leed_ll97_report.normalize import (
        normalize_address, normalize_borough, normalize_zip,
        normalize_building_name, normalize_bbl, normalize_bin,
    )

    path = config.RAW_LEED / "leed_nyc.csv"
    if not path.exists():
        path = latest_raw_file(config.RAW_LEED, "leed")
    if not path:
        logger.warning("No LEED data found in %s", config.RAW_LEED)
        return pd.DataFrame()

    df = load_csv(path)

    # Normalize fields
    df["address_norm"] = df.get("address_raw", pd.Series(dtype=str)).apply(normalize_address)
    df["zip_norm"] = df.get("zip", pd.Series(dtype=str)).apply(normalize_zip)
    df["building_name_norm"] = df.get("building_name_raw", pd.Series(dtype=str)).apply(normalize_building_name)
    df["borough_norm"] = df.get("city", df.get("borough", pd.Series(dtype=str))).apply(normalize_borough)
    df["bbl_norm"] = df.get("bbl", pd.Series(dtype=str)).apply(normalize_bbl)
    df["bin_norm"] = df.get("bin", pd.Series(dtype=str)).apply(normalize_bin)

    if "source_name" not in df.columns:
        df["source_name"] = "LEED"

    logger.info("Cleaned LEED: %d records", len(df))
    return df


def clean_nyc_energy_grades(config) -> pd.DataFrame:
    """Clean and normalize NYC energy grades data."""
    from leed_ll97_report.io import load_csv, latest_raw_file
    from leed_ll97_report.normalize import (
        normalize_address, normalize_borough, normalize_zip,
        normalize_building_name, normalize_bbl, normalize_bin,
    )

    path = latest_raw_file(config.RAW_ENERGY_GRADES, "nyc_energy_grades")
    if not path:
        logger.warning("No energy grades data found in %s", config.RAW_ENERGY_GRADES)
        return pd.DataFrame()

    df = load_csv(path)

    # Map actual LL33 dataset columns to our schema
    # Actual columns: Block, Lot, Building_Class, Tax_Class, Building_Count,
    #   DOF_Gross_Square_Footage, Address, BoroughName, BBL, ENERGY STAR Score, LetterScore
    col_map = {
        "BBL": "bbl",
        "Address": "address_raw",
        "BoroughName": "borough",
        "ENERGY STAR Score": "energy_star_score",
        "LetterScore": "energy_grade",
        "DOF_Gross_Square_Footage": "gross_sqft",
        "Building_Class": "building_class",
    }
    # Also handle LL84-style column names in case the dataset format changes
    col_map_alt = {
        "Property Id": "property_id",
        "Property Name": "building_name_raw",
        "Address 1": "address_raw",
        "Borough": "borough",
        "Postcode": "zip",
        "NYC Borough, Block and Lot (BBL)": "bbl",
        "NYC Building Identification Number (BIN)": "bin",
        "Energy Star Score": "energy_star_score",
        "Letter Grade": "energy_grade",
        "Site EUI (kBtu/ft²)": "site_eui",
    }
    # Try exact match first, then case-insensitive
    existing_cols = {c.lower(): c for c in df.columns}
    rename_map = {}
    for src, dest in {**col_map_alt, **col_map}.items():
        if src in df.columns:
            rename_map[src] = dest
        elif src.lower() in existing_cols:
            rename_map[existing_cols[src.lower()]] = dest
    df = df.rename(columns=rename_map)

    # Generate source_id
    if "property_id" in df.columns:
        df["source_id"] = "NYC_" + df["property_id"].astype(str)
    else:
        df["source_id"] = "NYC_" + df.index.astype(str)

    df["source_name"] = "NYC_ENERGY_GRADES"

    # Normalize fields
    for col, func in [
        ("address_raw", normalize_address),
        ("zip", normalize_zip),
        ("building_name_raw", normalize_building_name),
        ("borough", normalize_borough),
        ("bbl", normalize_bbl),
        ("bin", normalize_bin),
    ]:
        if col in df.columns:
            norm_col = col.replace("_raw", "_norm") if "_raw" in col else f"{col}_norm"
            df[norm_col] = df[col].apply(func)

    # Normalize energy grade
    if "energy_grade" in df.columns:
        df["energy_grade"] = df["energy_grade"].astype(str).str.strip().str.upper()
        df["energy_grade"] = df["energy_grade"].where(df["energy_grade"].isin(["A", "B", "C", "D"]), None)

    logger.info("Cleaned NYC energy grades: %d records", len(df))
    return df


def clean_nyc_benchmarking(config) -> pd.DataFrame:
    """Clean and normalize NYC benchmarking data."""
    from leed_ll97_report.io import load_csv, latest_raw_file
    from leed_ll97_report.normalize import (
        normalize_address, normalize_borough, normalize_zip,
        normalize_building_name, normalize_bbl, normalize_bin,
    )

    path = latest_raw_file(config.RAW_BENCHMARKING, "nyc_benchmarking")
    if not path:
        logger.warning("No benchmarking data found in %s", config.RAW_BENCHMARKING)
        return pd.DataFrame()

    df = load_csv(path)

    # Actual LL84 benchmarking columns (265 cols). Key ones:
    #   Property Name, Address 1, Borough, Postal Code,
    #   NYC Borough, Block and Lot (BBL), NYC Building Identification Number (BIN),
    #   ENERGY STAR Score, Site EUI (kBtu/ft²),
    #   Total (Location-Based) GHG Emissions (Metric Tons CO2e)
    col_map = {
        "Property Name": "building_name_raw",
        "Address 1": "address_raw",
        "Borough": "borough",
        "Postal Code": "zip",
        "Postcode": "zip",
        "NYC Borough, Block and Lot (BBL)": "bbl",
        "NYC Building Identification Number (BIN)": "bin",
        "Site EUI (kBtu/ft²)": "site_eui",
        "Weather Normalized Site EUI (kBtu/ft²)": "weather_norm_site_eui",
        "Total (Location-Based) GHG Emissions (Metric Tons CO2e)": "ghg_emissions_tco2e",
        "ENERGY STAR Score": "energy_star_score",
        "Year Ending": "year",
        "Largest Property Use Type": "property_type",
    }
    existing_cols = {c.lower(): c for c in df.columns}
    rename_map = {}
    for src, dest in col_map.items():
        if src.lower() in existing_cols:
            rename_map[existing_cols[src.lower()]] = dest
    df = df.rename(columns=rename_map)

    if "property_id" in df.columns:
        df["source_id"] = "BENCH_" + df["property_id"].astype(str)
    else:
        df["source_id"] = "BENCH_" + df.index.astype(str)

    df["source_name"] = "NYC_BENCHMARKING"

    for col, func in [
        ("address_raw", normalize_address),
        ("zip", normalize_zip),
        ("building_name_raw", normalize_building_name),
        ("borough", normalize_borough),
        ("bbl", normalize_bbl),
        ("bin", normalize_bin),
    ]:
        if col in df.columns:
            norm_col = col.replace("_raw", "_norm") if "_raw" in col else f"{col}_norm"
            df[norm_col] = df[col].apply(func)

    logger.info("Cleaned NYC benchmarking: %d records", len(df))
    return df


def clean_nyc_ll97(config) -> pd.DataFrame:
    """Clean and normalize NYC LL97 data."""
    from leed_ll97_report.io import load_csv, latest_raw_file
    from leed_ll97_report.normalize import (
        normalize_address, normalize_borough, normalize_zip,
        normalize_building_name, normalize_bbl, normalize_bin,
    )

    path = latest_raw_file(config.RAW_LL97, "nyc_ll97")
    if not path:
        logger.warning("No LL97 data found in %s", config.RAW_LL97)
        return pd.DataFrame()

    df = load_csv(path)

    # LL97 actual columns: Block, Lot, TaxClass, BldgClass, GBA,
    #   Building_Count, Address, BBL, Borough
    # Note: this dataset is a covered buildings list (no emissions values);
    # emissions data comes from the benchmarking dataset
    col_map = {
        "BBL": "bbl",
        "Address": "address_raw",
        "Borough": "borough",
        "GBA": "gross_building_area",
        "BldgClass": "building_class",
        "TaxClass": "tax_class",
        # Also handle alternative column names from other LL97 dataset formats
        "BIN": "bin",
        "Postcode": "zip",
        "Actual Emissions (tCO2e)": "ghg_emissions_tco2e",
        "Emissions Limit (tCO2e)": "ll97_limit_tco2e",
    }
    existing_cols = {c.lower(): c for c in df.columns}
    rename_map = {}
    for src, dest in col_map.items():
        if src.lower() in existing_cols:
            rename_map[existing_cols[src.lower()]] = dest
    df = df.rename(columns=rename_map)

    if "bbl" in df.columns:
        df["source_id"] = "LL97_" + df["bbl"].astype(str)
    else:
        df["source_id"] = "LL97_" + df.index.astype(str)

    df["source_name"] = "NYC_LL97"

    for col, func in [
        ("address_raw", normalize_address),
        ("zip", normalize_zip),
        ("building_name_raw", normalize_building_name),
        ("borough", normalize_borough),
        ("bbl", normalize_bbl),
        ("bin", normalize_bin),
    ]:
        if col in df.columns:
            norm_col = col.replace("_raw", "_norm") if "_raw" in col else f"{col}_norm"
            df[norm_col] = df[col].apply(func)

    # Compute overage
    if "ghg_emissions_tco2e" in df.columns and "ll97_limit_tco2e" in df.columns:
        df["ghg_emissions_tco2e"] = pd.to_numeric(df["ghg_emissions_tco2e"], errors="coerce")
        df["ll97_limit_tco2e"] = pd.to_numeric(df["ll97_limit_tco2e"], errors="coerce")
        df["ll97_overage_tco2e"] = df["ghg_emissions_tco2e"] - df["ll97_limit_tco2e"]

    logger.info("Cleaned NYC LL97: %d records", len(df))
    return df


def main():
    config = get_config()
    setup_logging()

    logger.info("=== Step 5: Clean and Normalize ===")

    from leed_ll97_report.io import save_csv

    leed = clean_leed(config)
    grades = clean_nyc_energy_grades(config)
    bench = clean_nyc_benchmarking(config)
    ll97 = clean_nyc_ll97(config)

    config.CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    for name, df in [("leed", leed), ("nyc_energy_grades", grades),
                     ("nyc_benchmarking", bench), ("nyc_ll97", ll97)]:
        if not df.empty:
            save_csv(df, config.CLEANED_DIR / f"{name}_cleaned.csv")
        else:
            logger.warning("Skipping empty dataset: %s", name)

    logger.info("Cleaning complete")


if __name__ == "__main__":
    main()
