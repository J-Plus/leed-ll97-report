"""
Compute headline stats and summary tables from the master matched dataset.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_all_metrics(master: pd.DataFrame, year: int) -> dict[str, pd.DataFrame]:
    """
    Compute all metrics and return a dict of summary DataFrames.

    Keys:
        headline: single-row headline stats
        leed_by_grade: count of LEED buildings by energy grade
        leed_level_by_grade: cross-tab of LEED level × energy grade
        ll97_overage_summary: LL97 overage statistics for matched buildings
        match_coverage_stats: match method and confidence breakdown
    """
    results = {}

    # ── Headline stats ─────────────────────────────────────────────────────
    total_leed = len(master)
    has_grade = master["energy_grade"].notna() & (master["energy_grade"] != "")
    matched_with_grade = has_grade.sum()

    grade_cd = master["energy_grade"].isin(["C", "D"])
    pct_cd = (grade_cd.sum() / matched_with_grade * 100) if matched_with_grade > 0 else 0

    has_ll97 = master["ghg_emissions_tco2e"].notna()
    has_limit = master["ll97_limit_tco2e"].notna()
    above_limit = (
        master["ghg_emissions_tco2e"] > master["ll97_limit_tco2e"]
    ) & has_ll97 & has_limit
    pct_above_limit = (above_limit.sum() / has_ll97.sum() * 100) if has_ll97.sum() > 0 else 0

    headline = pd.DataFrame([{
        "report_year": year,
        "total_leed_buildings": total_leed,
        "matched_with_grade": int(matched_with_grade),
        "match_rate_pct": round(matched_with_grade / total_leed * 100, 1) if total_leed > 0 else 0,
        "pct_grade_c_or_d": round(pct_cd, 1),
        "count_grade_c_or_d": int(grade_cd.sum()),
        "leed_with_ll97_data": int(has_ll97.sum()),
        "pct_above_ll97_limit": round(pct_above_limit, 1),
        "count_above_ll97_limit": int(above_limit.sum()),
    }])
    results["headline"] = headline

    # ── LEED by grade ──────────────────────────────────────────────────────
    grade_order = ["A", "B", "C", "D"]
    leed_by_grade = (
        master[has_grade]
        .groupby("energy_grade")
        .size()
        .reindex(grade_order, fill_value=0)
        .reset_index(name="count")
    )
    leed_by_grade.columns = ["energy_grade", "count"]
    total = leed_by_grade["count"].sum()
    leed_by_grade["pct"] = (leed_by_grade["count"] / total * 100).round(1) if total > 0 else 0
    results["leed_by_grade"] = leed_by_grade

    # ── LEED level × grade cross-tab ──────────────────────────────────────
    level_order = ["Platinum", "Gold", "Silver", "Certified"]
    if has_grade.any():
        xtab = pd.crosstab(
            master.loc[has_grade, "leed_level"],
            master.loc[has_grade, "energy_grade"],
        )
        # Reindex to standard order
        xtab = xtab.reindex(index=level_order, columns=grade_order, fill_value=0)
        xtab["total"] = xtab.sum(axis=1)
        results["leed_level_by_grade"] = xtab.reset_index()
    else:
        results["leed_level_by_grade"] = pd.DataFrame(
            columns=["leed_level"] + grade_order + ["total"]
        )

    # ── LL97 overage summary ──────────────────────────────────────────────
    ll97_rows = master[has_ll97 & has_limit].copy()
    if len(ll97_rows) > 0:
        ll97_rows["overage"] = ll97_rows["ghg_emissions_tco2e"] - ll97_rows["ll97_limit_tco2e"]
        ll97_summary = pd.DataFrame([{
            "buildings_with_ll97_data": len(ll97_rows),
            "above_limit": int((ll97_rows["overage"] > 0).sum()),
            "below_limit": int((ll97_rows["overage"] <= 0).sum()),
            "mean_overage_tco2e": round(ll97_rows.loc[ll97_rows["overage"] > 0, "overage"].mean(), 1)
            if (ll97_rows["overage"] > 0).any()
            else 0,
            "median_overage_tco2e": round(ll97_rows.loc[ll97_rows["overage"] > 0, "overage"].median(), 1)
            if (ll97_rows["overage"] > 0).any()
            else 0,
            "max_overage_tco2e": round(ll97_rows["overage"].max(), 1),
            "total_overage_tco2e": round(ll97_rows.loc[ll97_rows["overage"] > 0, "overage"].sum(), 1)
            if (ll97_rows["overage"] > 0).any()
            else 0,
        }])
    else:
        ll97_summary = pd.DataFrame([{
            "buildings_with_ll97_data": 0,
            "above_limit": 0,
            "below_limit": 0,
            "mean_overage_tco2e": 0,
            "median_overage_tco2e": 0,
            "max_overage_tco2e": 0,
            "total_overage_tco2e": 0,
        }])
    results["ll97_overage_summary"] = ll97_summary

    # ── Match coverage stats ──────────────────────────────────────────────
    method_counts = (
        master.groupby("match_method")
        .agg(
            count=("match_method", "size"),
            avg_confidence=("match_confidence", "mean"),
        )
        .reset_index()
    )
    method_counts["avg_confidence"] = method_counts["avg_confidence"].round(1)
    results["match_coverage_stats"] = method_counts

    # ── Certification age vs grade (for degradation analysis) ─────────────
    if "leed_cert_year" in master.columns and has_grade.any():
        age_df = master[has_grade & master["leed_cert_year"].notna()].copy()
        age_df["cert_age"] = year - age_df["leed_cert_year"]
        age_grade = age_df.groupby(["cert_age", "energy_grade"]).size().reset_index(name="count")
        results["cert_age_vs_grade"] = age_grade

    return results


def compute_degradation_correlation(master: pd.DataFrame, year: int) -> dict:
    """Compute correlation between certification age and energy grade."""
    grade_numeric = {"A": 4, "B": 3, "C": 2, "D": 1}
    df = master[
        master["energy_grade"].isin(grade_numeric.keys())
        & master["leed_cert_year"].notna()
    ].copy()

    if len(df) < 5:
        return {"correlation": None, "n": len(df), "note": "Insufficient data"}

    df["grade_num"] = df["energy_grade"].map(grade_numeric)
    df["cert_age"] = year - df["leed_cert_year"]

    corr = df["cert_age"].corr(df["grade_num"])
    return {
        "correlation": round(corr, 3) if not np.isnan(corr) else None,
        "n": len(df),
        "note": "Negative correlation = older certifications tend to have lower grades",
    }
