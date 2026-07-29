"""
Chart Generator — Create OEE and production visualization charts.

Phase 3+: Updated to use chart_templates for trend analysis charts,
maintains backwards compatibility with existing create_oee_trend_chart
and create_downtime_pie_chart signatures.
"""

import matplotlib
matplotlib.use("Agg")
from typing import Optional

from .oee_calculator import OEEResult, calculate_oee
from .chart_templates import (
    create_oee_trend_chart as _new_oee_trend_chart,
    create_pareto_chart,
    create_control_chart,
)


def create_oee_trend_chart(results: list[OEEResult], dates: list[str], title: str = "OEE Trend") -> Optional[str]:
    """
    Create an OEE trend chart with component breakdown.
    
    Backwards-compatible wrapper around chart_templates version.

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
        # Convert OEEResult objects to dict format for templates
        template_data = [
            {
                "date": dates[i],
                "oee": results[i].oee,
                "availability": results[i].availability,
                "performance": results[i].performance,
                "quality": results[i].quality,
            }
            for i in range(len(results))
        ]

        chart_path = _new_oee_trend_chart(
            template_data,
            title=title,
            show_forecast=False,  # Keep old behavior default
        )

        return chart_path

    except Exception as e:
        print(f"❌ Chart generation failed: {e}")
        return None


def create_trend_analysis_charts(
    oee_values: list[float],
    availability_values: list[float],
    performance_values: list[float],
    quality_values: list[float],
    dates: list[str],
    forecast: bool = True,
) -> list[str]:
    """
    Create a suite of trend analysis charts.
    
    Phase 3+: Returns list of chart paths including forecast, control, and Pareto.
    
    Args:
        oee_values: OEE time series
        availability_values: Availability time series
        performance_values: Performance time series
        quality_values: Quality time series
        dates: Date strings
        forecast: Whether to include forecast overlay
    
    Returns:
        List of chart file paths
    """
    charts = []

    if len(oee_values) < 2:
        return charts

    # OEE trend chart
    oee_data = [
        {
            "date": dates[i],
            "oee": oee_values[i],
            "availability": availability_values[i],
            "performance": performance_values[i],
            "quality": quality_values[i],
        }
        for i in range(len(oee_values))
    ]

    trend_path = _new_oee_trend_chart(oee_data, show_forecast=forecast)
    if trend_path:
        charts.append(trend_path)

    # Control chart
    control_path = create_control_chart(oee_values, dates)
    if control_path:
        charts.append(control_path)

    return charts


def create_downtime_pie_chart(downtime_reasons: dict[str, float], title: str = "Downtime Breakdown") -> Optional[str]:
    """
    Create a pie chart showing downtime reasons.
    
    Backwards-compatible wrapper around chart_templates version.
    
    Args:
        downtime_reasons: Dictionary mapping reasons to minutes
        title: Chart title
    
    Returns:
        Path to saved chart image, or None if failed
    """
    if not downtime_reasons:
        return None
    
    try:
        chart_path = create_pareto_chart(
            list(downtime_reasons.keys()),
            list(downtime_reasons.values()),
            title=title,
        )
        return chart_path
    except Exception as e:
        print(f"❌ Downtime chart generation failed: {e}")
        return None
