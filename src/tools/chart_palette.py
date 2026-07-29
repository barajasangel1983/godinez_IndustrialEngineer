"""
Chart Palette — Reusable matplotlib styling for consistent production charts.

Provides a centralized color scheme and style configuration for all charts,
ensuring visual consistency across the application.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from typing import Optional


# ── Color Palette ──────────────────────────────────────────────
PALETTE = {
    # Primary colors
    "oee": "#2E86AB",          # Steel blue for OEE
    "availability": "#A23B72",  # Purple for availability
    "performance": "#F18F01",   # Orange for performance
    "quality": "#C73E1D",       # Red for quality

    # Trend colors
    "trend_up": "#27AE60",      # Green for positive trend
    "trend_down": "#E74C3C",    # Red for negative trend
    "trend_stable": "#95A5A6",  # Gray for stable

    # Chart colors
    "bar_fill": "#3498DB",
    "bar_edge": "#2980B9",
    "line_main": "#2C3E50",
    "grid": "#ECF0F1",
    "background": "#FFFFFF",
    "text_primary": "#2C3E50",
    "text_secondary": "#7F8C8D",

    # Threshold colors
    "critical": "#E74C3C",
    "warning": "#F39C12",
    "good": "#27AE60",
    "world_class": "#2ECC71",

    # Control chart
    "ucl": "#E74C3C",           # Upper control limit
    "lcl": "#E74C3C",           # Lower control limit
    "center": "#2C3E50",        # Center line

    # Pareto
    "bar_primary": "#3498DB",
    "bar_secondary": "#ECF0F1",
    "line_primary": "#E74C3C",
}

# ── Style Configuration ────────────────────────────────────────
CHART_STYLE = {
    "figure": {
        "figsize": (12, 7),
        "dpi": 150,
        "facecolor": PALETTE["background"],
        "edgecolor": "white",
    },
    "axes": {
        "grid": True,
        "grid_alpha": 0.3,
        "axisbelow": True,
        "title_fontsize": 14,
        "label_fontsize": 11,
        "tick_fontsize": 9,
    },
    "legend": {
        "fontsize": 10,
        "framealpha": 0.9,
        "fancybox": True,
    },
    "font": {
        "family": "sans-serif",
        "size": 11,
        "weight": "normal",
    },
}


def apply_style():
    """Apply the chart style configuration to matplotlib."""
    plt.style.use("default")
    plt.rcParams.update({
        "figure.figsize": CHART_STYLE["figure"]["figsize"],
        "figure.dpi": CHART_STYLE["figure"]["dpi"],
        "figure.facecolor": CHART_STYLE["figure"]["facecolor"],
        "grid.alpha": CHART_STYLE["axes"]["grid_alpha"],
        "grid.linestyle": "--",
        "legend.fontsize": CHART_STYLE["legend"]["fontsize"],
        "legend.framealpha": CHART_STYLE["legend"]["framealpha"],
        "axes.grid": CHART_STYLE["axes"]["grid"],
        "axes.axisbelow": CHART_STYLE["axes"]["axisbelow"],
        "axes.titlepad": 10,
        "font.family": CHART_STYLE["font"]["family"],
        "font.size": CHART_STYLE["font"]["size"],
    })


def get_color(name: str, alpha: float = 1.0) -> str:
    """Get a color from the palette."""
    if name in PALETTE:
        return PALETTE[name]
    return name  # Return as-is if it's already a valid matplotlib color


def create_custom_cmap(name: str, colors: list[str], n: int = 256) -> LinearSegmentedColormap:
    """Create a custom colormap from a list of colors."""
    return LinearSegmentedColormap.from_list(name, colors, N=n)


def save_chart(fig, path: str = "/tmp/chart.png", bbox: str = "tight") -> str:
    """Save a matplotlib figure to disk."""
    try:
        plt.savefig(path, dpi=150, bbox_inches=bbox)
        plt.close(fig)
        return path
    except Exception:
        plt.close(fig)
        return ""


def make_title(
    title: str,
    subtitle: Optional[str] = None,
    fontsize: int = 14,
) -> tuple[str, Optional[str]]:
    """Format chart title with optional subtitle."""
    return title, subtitle


def add_threshold_line(
    ax,
    value: float,
    label: str = "",
    color: str = PALETTE["critical"],
    linestyle: str = "--",
    alpha: float = 0.5,
) -> None:
    """Add a threshold reference line to an axis."""
    ax.axhline(y=value, color=color, linestyle=linestyle, alpha=alpha, label=label)


def add_vertical_separator(
    ax,
    dates: list,
    marker_dates: list,
    color: str = PALETTE["grid"],
) -> None:
    """Add vertical separator lines at marker dates."""
    for d in marker_dates:
        if d in dates:
            x = dates.index(d)
            ax.axvline(x=x, color=color, linestyle=":", alpha=0.3)


def format_percent(value: float, decimals: int = 1) -> str:
    """Format a value as a percentage string."""
    return f"{value:.{decimals}f}%"


def format_number(value: float, decimals: int = 0) -> str:
    """Format a number with thousand separators."""
    return f"{value:,.{decimals}f}"


# Apply style on import
apply_style()
