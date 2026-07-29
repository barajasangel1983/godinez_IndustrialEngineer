"""
Trend Analysis Node — Statistical trend analysis for production data.

Runs on 'trend' intent. Uses the trend_engine for:
- Linear regression trend detection
- Anomaly detection (z-score method)
- Moving averages
- Pareto analysis
- Forecasting (linear projection)
"""

import numpy as np
from ..state import GodinezState
from ...tools.csv_reader import read_production_csv, filter_by_machine, filter_by_date
from ...tools.analysis.trend_engine import TrendEngine


def trend_analysis_node(state: GodinezState) -> dict:
    """
    Run trend analysis on production data.

    Extracts machine/date from entities, computes trend metrics,
    anomalies, and forecasts. Returns results dict for response formatting.
    """
    query = state.get("query", "")
    entities = state.get("entities", {})
    errors = state.get("errors", [])

    try:
        # Load data
        csv_path = state.get("csv_path", "data/synthetic_production.csv")
        rows = read_production_csv(csv_path)

        # Filter by machine if specified
        machine = entities.get("machine")
        if machine:
            rows = filter_by_machine(rows, machine)

        # Filter by date range if specified
        start_date = entities.get("start_date")
        end_date = entities.get("end_date")
        if start_date and end_date:
            rows = filter_by_date(rows, start_date, end_date)
        elif start_date:
            rows = filter_by_date(rows, start_date, "2026-12-31")
        elif end_date:
            rows = filter_by_date(rows, "2020-01-01", end_date)

        if len(rows) < 7:
            return {
                "response": "⚠️ Insufficient data for trend analysis. Need at least 7 data points.",
                "errors": ["Insufficient data for trend analysis"],
                "metadata": {"trend_analysis": "insufficient_data"},
            }

        # Group by machine if multiple machines present
        machines = set(r["machine_id"] for r in rows)

        if len(machines) > 1 and not machine:
            # Aggregate across all machines for overall trend
            # First, calculate per-line OEE
            line_data = {}
            for m in sorted(machines):
                m_rows = [r for r in rows if r["machine_id"] == m]
                m_sorted = sorted(m_rows, key=lambda x: x["date"])
                line_data[m] = _calc_per_period_oee(m_rows)
        else:
            # Single machine analysis - use the actual machine name as key
            rows_sorted = sorted(rows, key=lambda x: x["date"])
            machine_key = machine if machine else "overall"
            line_data = {machine_key: _calc_per_period_oee(rows_sorted)}

        # Analyze each machine's trend
        all_trends = {}
        for machine_id, data in line_data.items():
            trend_result = TrendEngine.full_analysis(
                oee_values=data["oee"],
                avail_values=data["availability"],
                perf_values=data["performance"],
                qual_values=data["quality"],
                dates=data["dates"],
                downtime_categories=data.get("downtime_reasons"),
                downtime_values=data.get("downtime_counts"),
            )
            all_trends[machine_id] = trend_result

        # Build response
        parts = []

        for machine_id, trend in all_trends.items():
            parts.append(f"### {machine_id}")
            parts.append("")

            # Trend summary
            parts.append(f"**Overall Direction:** {trend.overall_direction}")
            parts.append(f"**Risk Level:** {trend.risk_level}")
            parts.append(f"**Key Finding:** {trend.key_finding}")
            parts.append("")

            # OEE Trend
            oee = trend.oee_trend
            parts.append(f"**OEE Trend:** {oee.direction} ({oee.slope:+.3f}/period)")
            parts.append(f"  - Current: {oee.current_value:.1f}%")
            parts.append(f"  - 7-day forecast: {oee.forecast_7d:.1f}%")
            parts.append(f"  - 30-day forecast: {oee.forecast_30d:.1f}%")
            parts.append(f"  - Fit (R²): {oee.r_squared:.3f}")
            parts.append(f"  - Improvement: {oee.improvement_pct:+.1f}%")
            parts.append("")

            # Component trends
            parts.append("**Component Trends:**")
            parts.append(f"  - Availability: {trend.availability_trend.direction} ({trend.availability_trend.slope:+.3f})")
            parts.append(f"  - Performance: {trend.performance_trend.direction} ({trend.performance_trend.slope:+.3f})")
            parts.append(f"  - Quality: {trend.quality_trend.direction} ({trend.quality_trend.slope:+.3f})")
            parts.append("")

            # Anomalies
            if trend.anomalies:
                parts.append("**Anomalies Detected:**")
                for anomaly in trend.anomalies[:5]:  # Top 5
                    parts.append(
                        f"  - {anomaly.date}: {anomaly.value:.1f}% "
                        f"({anomaly.severity}, z={anomaly.deviation:.1f})"
                    )
                parts.append("")

            # Pareto analysis (if available)
            if trend.downtime_pareto:
                pareto = trend.downtime_pareto
                parts.append(f"**Top Downtime Cause:** {pareto.categories[0]} "
                           f"({pareto.values[0]:.0f} min, {pareto.cumulative_pct[0]:.0f}% cumulative)")
                parts.append(f"**Top 20% of causes account for {pareto.top_20_pct:.0f}% of downtime**")
                parts.append("")

        response = "\n".join(parts)

        return {
            "response": response,
            "analysis_results": {"trend": [t.to_dict() for t in all_trends.values()]},
            "metadata": {
                "trend_analysis": "complete",
                "machines_analyzed": list(all_trends.keys()),
                "data_points": len(rows),
            },
        }

    except Exception as e:
        return {
            "response": f"⚠️ Trend analysis failed: {e}",
            "errors": [f"Trend analysis error: {e}"],
            "metadata": {"trend_analysis": "error"},
        }


def _calc_per_period_oee(rows: list[dict]) -> dict:
    """Calculate OEE per period (date) for a single machine."""
    from ...tools.oee_calculator import calculate_oee

    # Group by date
    by_date = {}
    for r in rows:
        date = r["date"]
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(r)

    oee = []
    availability = []
    performance = []
    quality = []
    dates = []
    downtime_reasons = []
    downtime_counts = []

    for date in sorted(by_date.keys()):
        periods = by_date[date]
        # Aggregate across shifts
        total_planned = sum(p["planned_minutes"] for p in periods)
        total_run = sum(p["actual_run_minutes"] for p in periods)
        total_downtime = sum(p["downtime_minutes"] for p in periods)
        total_count = sum(p["total_count"] for p in periods)
        good_count = sum(p["good_count"] for p in periods)
        ideal_cycle = np.median([p["ideal_cycle_time_seconds"] for p in periods])

        result = calculate_oee(
            planned_minutes=total_planned,
            actual_run_minutes=total_run,
            downtime_minutes=total_downtime,
            ideal_cycle_time_seconds=ideal_cycle,
            total_count=total_count,
            good_count=good_count,
        )

        oee.append(result.oee)
        availability.append(result.availability)
        performance.append(result.performance)
        quality.append(result.quality)
        dates.append(date)

        # Track downtime reasons
        for p in periods:
            reason = p.get("downtime_reason", "unknown")
            if reason not in downtime_reasons:
                downtime_reasons.append(reason)
                downtime_counts.append(0)
            idx = downtime_reasons.index(reason)
            downtime_counts[idx] += p["downtime_minutes"]

    return {
        "oee": oee,
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "dates": dates,
        "downtime_reasons": downtime_reasons,
        "downtime_counts": downtime_counts,
    }
