"""
Chart Templates — Reusable chart types for production analysis.

Provides standardized chart templates:
- OEE Trend with forecasting overlay
- Pareto chart for defect/downtime analysis
- Control chart (X-bar) with UCL/LCL
- Forecast overlay chart
"""

import os
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Union

from .chart_palette import (
    PALETTE, apply_style, save_chart,
    add_threshold_line, format_percent,
)


def _chart_path(filename: str) -> str:
    """Build a cross-platform temp-dir path for a generated chart image."""
    return os.path.join(tempfile.gettempdir(), filename)


def create_oee_trend_chart(
    results: list[dict],
    title: str = "OEE Trend Analysis",
    show_forecast: bool = False,
    forecast_days: int = 30,
) -> Optional[str]:
    """
    Create OEE trend chart with component breakdown and optional forecast.

    Args:
        results: List of dicts with keys: date, oee, availability, performance, quality
        title: Chart title
        show_forecast: Whether to show forecast overlay
        forecast_days: Number of days to forecast

    Returns:
        Path to saved chart image
    """
    if len(results) < 2:
        return None

    try:
        apply_style()

        dates = [datetime.strptime(r["date"], "%Y-%m-%d") for r in results]
        oee_scores = [r["oee"] for r in results]
        avail_scores = [r["availability"] for r in results]
        perf_scores = [r["performance"] for r in results]
        qual_scores = [r["quality"] for r in results]

        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=(14, 10),
            gridspec_kw={"height_ratios": [1, 1]},
        )
        fig.suptitle(title, fontsize=16, fontweight="bold")

        # Top plot: OEE components
        ax1.plot(dates, avail_scores, "o-", label="Availability", color=PALETTE["availability"], linewidth=2, markersize=4)
        ax1.plot(dates, perf_scores, "s-", label="Performance", color=PALETTE["performance"], linewidth=2, markersize=4)
        ax1.plot(dates, qual_scores, "D-", label="Quality", color=PALETTE["quality"], linewidth=2, markersize=4)
        ax1.plot(dates, oee_scores, "ko-", label="OEE", linewidth=3, markersize=5)

        # Add thresholds
        ax1.axhline(y=85, color=PALETTE["good"], linestyle=":", alpha=0.6, label="Good (85%)")
        ax1.axhline(y=75, color=PALETTE["warning"], linestyle=":", alpha=0.6, label="Warning (75%)")
        ax1.axhline(y=60, color=PALETTE["critical"], linestyle=":", alpha=0.6, label="Critical (60%)")

        ax1.set_ylabel("Percentage (%)")
        ax1.set_title("OEE Components Over Time")
        ax1.legend(loc="lower right")
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax1.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # Bottom plot: OEE score with rating
        oee_array = np.array(oee_scores)
        colors = []
        for oee in oee_scores:
            if oee >= 90:
                colors.append(PALETTE["world_class"])
            elif oee >= 85:
                colors.append(PALETTE["good"])
            elif oee >= 75:
                colors.append(PALETTE["warning"])
            else:
                colors.append(PALETTE["critical"])

        x_positions = range(len(dates))
        ax2.bar(x_positions, oee_scores, color=colors, alpha=0.7, edgecolor=PALETTE["bar_edge"])
        ax2.axhline(y=85, color=PALETTE["good"], linestyle="--", alpha=0.5)
        ax2.axhline(y=60, color=PALETTE["critical"], linestyle="--", alpha=0.5)

        ax2.set_ylabel("OEE Score (%)")
        ax2.set_title("Overall OEE Score")
        ax2.set_xticks(x_positions[::max(1, len(x_positions) // 10)])
        ax2.set_xticklabels(
            [dates[i].strftime("%m/%d") for i in x_positions[::max(1, len(x_positions) // 10)]],
            rotation=45, ha="right",
        )
        ax2.grid(True, alpha=0.3, axis="y")

        # Forecast overlay
        if show_forecast and len(oee_scores) >= 5:
            from .analysis.trend_engine import TrendEngine
            trend = TrendEngine.analyze_trend(oee_scores)

            forecast_start = len(oee_scores) - 1
            forecast_x = list(range(forecast_start, forecast_start + forecast_days + 1))
            forecast_y = []
            base = oee_scores[-1]
            trend_direction = {"up": 1, "down": -1, "stable": 0}.get(trend.direction, 0)
            for i in range(forecast_days + 1):
                val = base + trend.slope * (i + 1) * trend_direction
                forecast_y.append(max(0, min(100, round(val, 1))))

            ax1.plot(
                np.arange(forecast_start, forecast_start + forecast_days + 1),
                forecast_y,
                "r--", linewidth=2, alpha=0.6, label="Forecast",
            )
            ax1.fill_between(
                np.arange(forecast_start, forecast_start + forecast_days + 1),
                [max(0, v - 5) for v in forecast_y],
                [min(100, v + 5) for v in forecast_y],
                alpha=0.15, color="red",
            )

        plt.tight_layout()
        return save_chart(fig, _chart_path("oee_trend_chart.png"))

    except Exception as e:
        print(f"❌ OEE trend chart generation failed: {e}")
        plt.close(fig)
        return None


def create_pareto_chart(
    categories: list[str],
    values: list[float],
    title: str = "Pareto Analysis",
    unit: str = "minutes",
) -> Optional[str]:
    """
    Create a Pareto chart showing top contributors.

    Args:
        categories: Category names (e.g., downtime reasons)
        values: Numeric values for each category
        title: Chart title
        unit: Unit label (e.g., "minutes", "units", "dollars")

    Returns:
        Path to saved chart image
    """
    if not categories or not values:
        return None

    try:
        apply_style()

        # Sort by value descending
        sorted_pairs = sorted(zip(categories, values), key=lambda x: x[1], reverse=True)
        categories = [p[0] for p in sorted_pairs]
        values = [p[1] for p in sorted_pairs]

        total = sum(values)
        cumulative = np.cumsum(values) / total * 100

        fig, ax1 = plt.subplots(figsize=(12, 7))

        # Bars
        bar_color = PALETTE["bar_primary"]
        bars = ax1.bar(range(len(categories)), values, color=bar_color, alpha=0.7, edgecolor=PALETTE["bar_edge"])

        ax1.set_xlabel("Downtime Reason")
        ax1.set_ylabel(f"Downtime ({unit})", color=PALETTE["text_primary"])
        ax1.set_title(title, fontweight="bold")
        ax1.set_xticks(range(len(categories)))
        ax1.set_xticklabels(categories, rotation=45, ha="right")

        # Percentage line
        ax2 = ax1.twinx()
        ax2.plot(range(len(categories)), cumulative, "ro-", linewidth=2, markersize=6, label="Cumulative %")
        ax2.set_ylabel("Cumulative %", color="red")
        ax2.axhline(y=80, color=PALETTE["warning"], linestyle=":", alpha=0.5, label="80% threshold")
        ax2.set_ylim(0, 110)

        # Add 80/20 annotation
        for i, cum in enumerate(cumulative):
            if cum >= 80:
                ax2.annotate(f"20% of causes → {cum:.0f}% of impact",
                           xy=(i, cum), xytext=(i + 2, cum - 15),
                           arrowprops=dict(arrowstyle="->", color=PALETTE["warning"]),
                           fontsize=9, color=PALETTE["warning"], fontweight="bold")
                break

        ax1.grid(True, alpha=0.3, axis="y")
        ax2.grid(False)

        # Add total annotation
        ax1.text(0.02, 0.95, f"Total: {total:.0f} {unit}", transform=ax1.transAxes,
                fontsize=10, verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor=PALETTE["bar_secondary"], alpha=0.7))

        plt.tight_layout()
        return save_chart(fig, _chart_path("pareto_chart.png"))

    except Exception as e:
        print(f"❌ Pareto chart generation failed: {e}")
        plt.close("all")
        return None


def create_control_chart(
    data: list[float],
    dates: list[str],
    title: str = "OEE Control Chart (X-bar)",
) -> Optional[str]:
    """
    Create a control chart with UCL, LCL, and center line.

    Args:
        data: Time series values
        dates: Corresponding dates
        title: Chart title

    Returns:
        Path to saved chart image
    """
    if len(data) < 5:
        return None

    try:
        apply_style()

        dates = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
        data_array = np.array(data)

        # Calculate statistics
        mean = np.mean(data_array)
        std = np.std(data_array)
        ucl = mean + 3 * std
        lcl = max(0, mean - 3 * std)  # Clamp to 0

        fig, ax = plt.subplots(figsize=(14, 6))
        fig.suptitle(title, fontsize=14, fontweight="bold")

        # Plot data
        ax.plot(dates, data_array, "bo-", label="OEE", linewidth=2, markersize=4)

        # Control limits
        ax.axhline(y=mean, color=PALETTE["center"], linestyle="-", linewidth=2, label=f"Center ({mean:.1f}%)")
        ax.axhline(y=ucl, color=PALETTE["ucl"], linestyle="--", linewidth=1.5, label=f"UCL ({ucl:.1f}%)")
        ax.axhline(y=lcl, color=PALETTE["lcl"], linestyle="--", linewidth=1.5, label=f"LCL ({lcl:.1f}%)")

        # Highlight points outside control limits
        outliers = [i for i, v in enumerate(data_array) if v > ucl or v < lcl]
        if outliers:
            outlier_dates = [dates[i] for i in outliers]
            outlier_vals = [data_array[i] for i in outliers]
            ax.scatter(outlier_dates, outlier_vals, color="red", s=100, zorder=5, label=f"Out-of-control ({len(outliers)})")

        ax.set_ylabel("OEE (%)")
        ax.legend(loc="lower right", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # Add stats box
        stats_text = (
            f"Mean: {mean:.1f}%\n"
            f"Std: {std:.1f}%\n"
            f"Min: {data_array.min():.1f}%\n"
            f"Max: {data_array.max():.1f}%"
        )
        ax.text(0.98, 0.95, stats_text, transform=ax.transAxes,
               fontsize=9, verticalalignment="top", horizontalalignment="right",
               bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

        plt.tight_layout()
        return save_chart(fig, _chart_path("control_chart.png"))

    except Exception as e:
        print(f"❌ Control chart generation failed: {e}")
        plt.close("all")
        return None


def create_forecast_chart(
    history: list[dict],
    forecast: list[dict],
    title: str = "Production Forecast",
) -> Optional[str]:
    """
    Create a chart showing historical data with forecast overlay.

    Args:
        history: List of dicts with 'date' and 'value' keys
        forecast: List of dicts with 'date' and 'value' keys
        title: Chart title

    Returns:
        Path to saved chart image
    """
    if not history:
        return None

    try:
        apply_style()

        hist_dates = [datetime.strptime(h["date"], "%Y-%m-%d") for h in history]
        hist_values = [h["value"] for h in history]
        fore_dates = [datetime.strptime(f["date"], "%Y-%m-%d") for f in forecast]
        fore_values = [f["value"] for f in forecast]

        fig, ax = plt.subplots(figsize=(14, 6))
        fig.suptitle(title, fontsize=14, fontweight="bold")

        # Historical data
        ax.plot(hist_dates, hist_values, "bo-", label="Historical", linewidth=2, markersize=4)

        # Forecast
        ax.plot(fore_dates, fore_values, "r--", label="Forecast", linewidth=2, markersize=6)

        # Fill confidence interval
        if len(fore_values) >= 2:
            std = np.std(hist_values[-30:]) if len(hist_values) >= 30 else np.std(hist_values) * 0.5
            upper = [v + std for v in fore_values]
            lower = [max(0, v - std) for v in fore_values]
            ax.fill_between(fore_dates, lower, upper, alpha=0.15, color="red", label="±1σ Confidence")

        ax.set_ylabel("Value")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # Add arrow annotation
        if fore_values:
            last_forecast = fore_values[-1]
            ax.annotate(f"End: {last_forecast:.1f}",
                       xy=(fore_dates[-1], last_forecast),
                       xytext=(fore_dates[-1] - timedelta(days=10), last_forecast + max(0.5 * std, 2)),
                       arrowprops=dict(arrowstyle="->", color="red"),
                       fontsize=10, color="red", fontweight="bold")

        plt.tight_layout()
        return save_chart(fig, _chart_path("forecast_chart.png"))

    except Exception as e:
        print(f"❌ Forecast chart generation failed: {e}")
        plt.close("all")
        return None


def create_trend_line_chart(
    dates: list[str],
    series: dict[str, list[float]],
    title: str = "Production Trends",
) -> Optional[str]:
    """
    Create a multi-series line chart for trend comparison.

    Args:
        dates: Date strings
        series: Dict mapping series names to value lists
        title: Chart title

    Returns:
        Path to saved chart image
    """
    if not dates or not series:
        return None

    try:
        apply_style()

        colors = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#27AE60"]

        fig, ax = plt.subplots(figsize=(14, 7))
        fig.suptitle(title, fontsize=14, fontweight="bold")

        parsed_dates = [datetime.strptime(d, "%Y-%m-%d") for d in dates]

        for i, (name, values) in enumerate(series.items()):
            color = colors[i % len(colors)]
            ax.plot(parsed_dates, values, color=color, label=name, linewidth=2, markersize=3)

        ax.set_ylabel("Value")
        ax.set_xlabel("Date")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        plt.tight_layout()
        return save_chart(fig, _chart_path("trend_line_chart.png"))

    except Exception as e:
        print(f"❌ Trend line chart generation failed: {e}")
        plt.close("all")
        return None
