"""
Chart generation for the annual report.

All charts saved as PNGs to the outputs directory.
Uses matplotlib only.
"""

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Style constants ────────────────────────────────────────────────────────
GRADE_COLORS = {"A": "#2ecc71", "B": "#3498db", "C": "#f39c12", "D": "#e74c3c"}
LEED_COLORS = {
    "Platinum": "#8e8e8e",
    "Gold": "#f1c40f",
    "Silver": "#bdc3c7",
    "Certified": "#27ae60",
}
FIG_DPI = 150


def _save(fig: plt.Figure, path: Path):
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("Saved chart: %s", path.name)


def chart_grade_distribution(leed_by_grade: pd.DataFrame, output_dir: Path, year: int):
    """Bar chart: count of LEED buildings by energy grade."""
    fig, ax = plt.subplots(figsize=(8, 5))
    grades = leed_by_grade["energy_grade"]
    counts = leed_by_grade["count"]
    colors = [GRADE_COLORS.get(g, "#95a5a6") for g in grades]

    bars = ax.bar(grades, counts, color=colors, edgecolor="white", linewidth=1.2)
    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            str(int(count)),
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    ax.set_xlabel("Energy Grade")
    ax.set_ylabel("Number of LEED Buildings")
    ax.set_title(f"LEED-Certified Buildings by NYC Energy Grade ({year})")
    ax.spines[["top", "right"]].set_visible(False)

    _save(fig, output_dir / f"grade_distribution_{year}.png")


def chart_grade_by_leed_level(
    leed_level_by_grade: pd.DataFrame,
    output_dir: Path,
    year: int,
):
    """Stacked bar chart: energy grades broken down by LEED certification level."""
    fig, ax = plt.subplots(figsize=(10, 6))

    grade_cols = ["A", "B", "C", "D"]
    available = [c for c in grade_cols if c in leed_level_by_grade.columns]
    if not available:
        logger.warning("No grade columns for level-by-grade chart")
        plt.close(fig)
        return

    levels = leed_level_by_grade["leed_level"]
    bottom = np.zeros(len(levels))

    for grade in available:
        values = leed_level_by_grade[grade].values.astype(float)
        ax.bar(
            levels,
            values,
            bottom=bottom,
            label=f"Grade {grade}",
            color=GRADE_COLORS.get(grade, "#95a5a6"),
            edgecolor="white",
            linewidth=0.8,
        )
        bottom += values

    ax.set_xlabel("LEED Certification Level")
    ax.set_ylabel("Number of Buildings")
    ax.set_title(f"Energy Grade by LEED Level ({year})")
    ax.legend(title="Energy Grade")
    ax.spines[["top", "right"]].set_visible(False)

    _save(fig, output_dir / f"grade_by_leed_level_{year}.png")


def chart_ll97_overage_hist(master: pd.DataFrame, output_dir: Path, year: int):
    """Histogram of LL97 emissions overage for LEED buildings."""
    has_data = (
        master["ghg_emissions_tco2e"].notna() & master["ll97_limit_tco2e"].notna()
    )
    df = master[has_data].copy()

    if len(df) == 0:
        logger.warning("No LL97 data for overage histogram")
        return

    df["overage"] = df["ghg_emissions_tco2e"] - df["ll97_limit_tco2e"]

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#e74c3c" if v > 0 else "#2ecc71" for v in df["overage"]]

    ax.hist(
        df["overage"],
        bins=30,
        color="#3498db",
        edgecolor="white",
        alpha=0.8,
    )
    ax.axvline(0, color="#e74c3c", linestyle="--", linewidth=1.5, label="LL97 Limit")

    ax.set_xlabel("Emissions Overage (tCO2e)")
    ax.set_ylabel("Number of Buildings")
    ax.set_title(f"LL97 Emissions Overage for LEED Buildings ({year})")
    ax.legend()
    ax.spines[["top", "right"]].set_visible(False)

    _save(fig, output_dir / f"ll97_overage_hist_{year}.png")


def chart_grade_vs_cert_age(master: pd.DataFrame, output_dir: Path, year: int):
    """
    Box plot or scatter: energy grade vs certification age.
    Shows whether older LEED certifications correlate with worse grades.
    """
    has_grade = master["energy_grade"].isin(["A", "B", "C", "D"])
    has_year = master["leed_cert_year"].notna()
    df = master[has_grade & has_year].copy()

    if len(df) < 5:
        logger.warning("Insufficient data for grade vs cert age chart")
        return

    df["cert_age"] = year - df["leed_cert_year"]

    fig, ax = plt.subplots(figsize=(9, 5))

    grade_order = ["A", "B", "C", "D"]
    data_by_grade = [df[df["energy_grade"] == g]["cert_age"].dropna() for g in grade_order]
    data_by_grade = [d for d in data_by_grade if len(d) > 0]
    labels = [g for g, d in zip(grade_order, [df[df["energy_grade"] == g]["cert_age"].dropna() for g in grade_order]) if len(d) > 0]

    if data_by_grade:
        bp = ax.boxplot(
            data_by_grade,
            labels=labels,
            patch_artist=True,
            medianprops={"color": "black", "linewidth": 1.5},
        )
        for patch, label in zip(bp["boxes"], labels):
            patch.set_facecolor(GRADE_COLORS.get(label, "#95a5a6"))
            patch.set_alpha(0.7)

    ax.set_xlabel("Energy Grade")
    ax.set_ylabel("Years Since LEED Certification")
    ax.set_title(f"Certification Age by Energy Grade ({year})")
    ax.spines[["top", "right"]].set_visible(False)

    _save(fig, output_dir / f"grade_vs_cert_age_{year}.png")


def chart_match_confidence(master: pd.DataFrame, output_dir: Path, year: int):
    """Histogram of match confidence scores."""
    fig, ax = plt.subplots(figsize=(8, 5))

    confidences = master["match_confidence"].dropna()
    if len(confidences) == 0:
        logger.warning("No confidence data for histogram")
        plt.close(fig)
        return

    bins = [0, 50, 70, 80, 90, 100]
    labels_text = ["<50\n(Review)", "50-69\n(Name)", "70-79\n(Fuzzy)", "80-89\n(Fuzzy+)", "90-100\n(Exact/ID)"]
    counts, _ = np.histogram(confidences, bins=bins)

    bar_colors = ["#e74c3c", "#f39c12", "#f1c40f", "#3498db", "#2ecc71"]
    bars = ax.bar(range(len(counts)), counts, color=bar_colors, edgecolor="white", linewidth=1.2)

    ax.set_xticks(range(len(counts)))
    ax.set_xticklabels(labels_text, fontsize=9)
    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.3,
                str(int(count)),
                ha="center",
                va="bottom",
                fontweight="bold",
            )

    ax.set_xlabel("Match Confidence Range")
    ax.set_ylabel("Number of Buildings")
    ax.set_title(f"Match Confidence Distribution ({year})")
    ax.spines[["top", "right"]].set_visible(False)

    _save(fig, output_dir / f"match_confidence_breakdown_{year}.png")


def generate_all_charts(
    master: pd.DataFrame,
    metrics: dict[str, pd.DataFrame],
    output_dir: Path,
    year: int,
):
    """Generate all charts and save to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Generating charts in %s", output_dir)

    if "leed_by_grade" in metrics:
        chart_grade_distribution(metrics["leed_by_grade"], output_dir, year)

    if "leed_level_by_grade" in metrics:
        chart_grade_by_leed_level(metrics["leed_level_by_grade"], output_dir, year)

    chart_ll97_overage_hist(master, output_dir, year)
    chart_grade_vs_cert_age(master, output_dir, year)
    chart_match_confidence(master, output_dir, year)

    logger.info("All charts generated")
