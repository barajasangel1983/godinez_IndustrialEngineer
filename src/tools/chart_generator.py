"""
Chart Generator — Create OEE and production visualization charts
"""

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server environments
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from typing import Optional

from .oee_calculator import OEEResult, calculate_oee


def create_oee_trend_chart(results: list[OEEResult], dates: list[str], title: str = "OEE Trend") -> Optional[str]:
    """
    Create an OEE trend chart with component breakdown.
    
    Args:
        results: List of OEEResult objects
        dates: List of date strings
        title: Chart title
    
    Returns:
        Path to saved chart image, or None if failed
    """
    if len(results) < 2:
        return None
    
    try:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={"height_ratios": [1, 1]})
        fig.suptitle(title, fontsize=16, fontweight="bold")
        
        # Convert dates
        x_dates = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
        
        # Top plot: OEE components
        ax1.plot(x_dates, [r.availability for r in results], "b-o", label="Availability", linewidth=2)
        ax1.plot(x_dates, [r.performance for r in results], "g-o", label="Performance", linewidth=2)
        ax1.plot(x_dates, [r.quality for r in results], "r-o", label="Quality", linewidth=2)
        ax1.plot(x_dates, [r.oee for r in results], "k--", label="OEE", linewidth=3)
        
        # Add threshold lines
        ax1.axhline(y=85, color="green", linestyle=":", alpha=0.5, label="Good (85%)")
        ax1.axhline(y=75, color="orange", linestyle=":", alpha=0.5, label="Needs Improvement (75%)")
        ax1.axhline(y=60, color="red", linestyle=":", alpha=0.5, label="Critical (60%)")
        
        ax1.set_ylabel("Percentage (%)")
        ax1.set_title("OEE Components Over Time")
        ax1.legend(loc="lower right")
        ax1.grid(True, alpha=0.3)
        
        # Format x-axis
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax1.xaxis.set_major_locator(mdates.DayLocator())
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")
        
        # Bottom plot: OEE score with rating
        oee_scores = [r.oee for r in results]
        ax2.bar(range(len(x_dates)), oee_scores, color="steelblue", alpha=0.7)
        ax2.axhline(y=85, color="green", linestyle="--", alpha=0.5)
        ax2.axhline(y=60, color="red", linestyle="--", alpha=0.5)
        
        # Add rating labels
        ratings = [r.rating.replace("_", " ").title() for r in results]
        for i, (x, oee, rating) in enumerate(zip(range(len(x_dates)), oee_scores, ratings)):
            ax2.text(x, oee + 1, f"{oee:.1f}%\n{rating}", ha="center", fontsize=8)
        
        ax2.set_ylabel("OEE Score (%)")
        ax2.set_title("Overall OEE Score")
        ax2.set_xticks(range(len(x_dates)))
        ax2.set_xticklabels([d.strftime("%m/%d") for d in x_dates], rotation=45, ha="right")
        ax2.grid(True, alpha=0.3, axis="y")
        
        plt.tight_layout()
        
        # Save chart
        chart_path = "/tmp/oee_trend_chart.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()
        
        return chart_path
    
    except Exception as e:
        print(f"❌ Chart generation failed: {e}")
        return None


def create_downtime_pie_chart(downtime_reasons: dict[str, float], title: str = "Downtime Breakdown") -> Optional[str]:
    """
    Create a pie chart showing downtime reasons.
    
    Args:
        downtime_reasons: Dictionary mapping reasons to minutes
        title: Chart title
    
    Returns:
        Path to saved chart image, or None if failed
    """
    if not downtime_reasons:
        return None
    
    try:
        fig, ax = plt.subplots(figsize=(10, 8))
        
        reasons = list(downtime_reasons.keys())
        minutes = list(downtime_reasons.values())
        
        colors = plt.cm.Set3(range(len(reasons)))
        
        wedges, texts, autotexts = ax.pie(
            minutes,
            labels=reasons,
            autopct="%1.1f%%",
            colors=colors,
            startangle=90,
            textprops={"fontsize": 10}
        )
        
        ax.set_title(title, fontsize=14, fontweight="bold")
        
        # Calculate total and add summary
        total = sum(minutes)
        summary_text = f"Total Downtime: {total:.0f} minutes"
        ax.text(0.5, -0.1, summary_text, transform=ax.transAxes, 
                ha="center", fontsize=12, fontweight="bold")
        
        plt.tight_layout()
        
        chart_path = "/tmp/downtime_pie_chart.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()
        
        return chart_path
    
    except Exception as e:
        print(f"❌ Downtime chart generation failed: {e}")
        return None
