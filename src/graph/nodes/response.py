"""
Response node — Format and return the final response.

Phase 0: Simple string response with metadata.
Phase 3+: Trend analysis formatting, chart embedding, file attachment generation.
"""

import base64
import io
from ..state import GodinezState
from ...tools.chart_templates import create_oee_trend_chart, create_pareto_chart, create_control_chart
from ...tools.chart_palette import PALETTE, apply_style
from ...tools.data_paths import resolve_csv_path


def response_node(state: GodinezState) -> GodinezState:
    """Format and return the final response with trend analysis support."""

    response = state.get("response", "")
    intent = state.get("intent")
    errors = state.get("errors", [])
    attachments = list(state.get("attachments", []) or [])
    metadata = state.get("metadata", {})

    # Build a formatted response
    formatted = f"**Godínez IndustrialEngineer**\n"
    formatted += f"{'=' * 40}\n"
    formatted += f"Intent: {intent or 'unknown'}\n"
    formatted += f"LLM: {_describe_llm(metadata.get('classify_method'))}\n"
    formatted += f"\n{response}\n"

    # Generate trend charts if trend analysis was performed
    analysis_results = state.get("analysis_results", {})
    charts = []
    if intent == "trend" and analysis_results.get("trend"):
        charts = _generate_trend_charts(analysis_results, state)
        formatted += f"\n📊 Generated {len(charts)} trend chart(s)"
        attachments.extend([c["path"] for c in charts])

    if errors:
        formatted += f"\n⚠️ Errors encountered:\n"
        for err in errors:
            formatted += f"  - {err}\n"

    return {
        "response": formatted,
        "attachments": attachments if attachments else None,
        "charts": charts if charts else None,  # Base64-encoded chart data for API responses
        "metadata": {**state.get("metadata", {}), "phase": "3", "chart_count": len(charts)},
    }


_LLM_DISPLAY_NAMES = {
    "primary": "NVIDIA-Nemotron-Nano-9B-v2 (DGX)",
    "ollama": "qwen3:8b (Ollama fallback)",
    "keyword_fallback": "keyword matching (no LLM reachable)",
    "skipped_system_command": "n/a (system command)",
}


def _describe_llm(classify_method: str | None) -> str:
    """Map the classify node's llm_used value to a human-readable label."""
    return _LLM_DISPLAY_NAMES.get(classify_method, "unknown")


def _generate_trend_charts(analysis_results: dict, state: GodinezState) -> list[dict]:
    """Generate trend analysis charts and return file paths + base64 data."""
    charts = []
    csv_path = resolve_csv_path(state.get("csv_path"))

    try:
        from ...tools.csv_reader import read_production_csv
        rows = read_production_csv(csv_path)

        # Filter by date range from entities
        entities = state.get("entities", {})
        start_date = entities.get("start_date")
        end_date = entities.get("end_date")
        if start_date:
            rows = [r for r in rows if r["date"] >= start_date]
        if end_date:
            rows = [r for r in rows if r["date"] <= end_date]

        # Group by date for OEE trend
        by_date = {}
        for r in rows:
            date = r["date"]
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(r)

        # Calculate aggregate OEE per date
        trend_data = []
        for date in sorted(by_date.keys()):
            periods = by_date[date]
            total_planned = sum(p["planned_minutes"] for p in periods)
            total_run = sum(p["actual_run_minutes"] for p in periods)
            total_downtime = sum(p["downtime_minutes"] for p in periods)
            total_count = sum(p["total_count"] for p in periods)
            good_count = sum(p["good_count"] for p in periods)
            from ...tools.oee_calculator import calculate_oee
            result = calculate_oee(
                planned_minutes=total_planned,
                actual_run_minutes=total_run,
                downtime_minutes=total_downtime,
                ideal_cycle_time_seconds=next(iter(periods))["ideal_cycle_time_seconds"],
                total_count=total_count,
                good_count=good_count,
            )
            trend_data.append({
                "date": date,
                "oee": result.oee,
                "availability": result.availability,
                "performance": result.performance,
                "quality": result.quality,
            })

        # Generate OEE trend chart
        if trend_data:
            chart_path = create_oee_trend_chart(
                trend_data,
                title="OEE Trend Analysis",
                show_forecast=True,
            )
            if chart_path:
                b64 = _save_chart_to_base64(chart_path, "oee_trend")
                charts.append({"path": chart_path, "base64": b64, "type": "oee_trend", "filename": "oee_trend.png"})

        # Generate control chart
        oee_values = [d["oee"] for d in trend_data]
        oee_dates = [d["date"] for d in trend_data]
        if len(oee_values) >= 10:
            control_path = create_control_chart(oee_values, oee_dates)
            if control_path:
                b64 = _save_chart_to_base64(control_path, "control")
                charts.append({"path": control_path, "base64": b64, "type": "control", "filename": "control_chart.png"})

        # Generate Pareto chart from downtime reasons
        downtime_reasons = {}
        for r in rows:
            reason = r.get("downtime_reason", "unknown")
            downtime_reasons[reason] = downtime_reasons.get(reason, 0) + r["downtime_minutes"]

        if len(downtime_reasons) >= 2:
            pareto_path = create_pareto_chart(
                list(downtime_reasons.keys()),
                list(downtime_reasons.values()),
                title="Downtime Pareto Analysis",
            )
            if pareto_path:
                b64 = _save_chart_to_base64(pareto_path, "pareto")
                charts.append({"path": pareto_path, "base64": b64, "type": "pareto", "filename": "pareto_chart.png"})

    except Exception as e:
        print(f"⚠️ Chart generation failed: {e}")

    return charts


def _save_chart_to_base64(chart_path: str, chart_type: str) -> str:
    """Convert a saved chart image to base64 string."""
    try:
        with open(chart_path, "rb") as f:
            image_data = f.read()
        return base64.b64encode(image_data).decode("utf-8")
    except Exception as e:
        print(f"⚠️ Failed to convert chart {chart_type} to base64: {e}")
        return ""
