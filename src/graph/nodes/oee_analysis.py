"""
OEE Analysis Node — Calculate and analyze Overall Equipment Effectiveness

Phase 1: Full implementation with CSV data reading, OEE calculation, and chart generation.
"""

from pathlib import Path
from collections import defaultdict

from ..state import GodinezState
from ...tools.oee_calculator import calculate_oee, calculate_average_oee
from ...tools.csv_reader import read_production_csv
from ...tools.chart_generator import create_oee_trend_chart, create_downtime_pie_chart
from ...config import DATA_DIR


def oee_analysis_node(state: GodinezState) -> GodinezState:
    """
    Perform OEE analysis on production data.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updated state with OEE analysis results
    """
    
    errors = state.get("errors", [])
    attachments = state.get("attachments", [])
    metadata = state.get("metadata", {})
    
    try:
        # ── Step 1: Read production data ─────────────────
        csv_path = DATA_DIR / "sample_production.csv"
        
        if not csv_path.exists():
            errors.append(f"Production data CSV not found: {csv_path}")
            return {
                "response": "Production data file not found. Please ensure sample_production.csv exists in the data directory.",
                "errors": errors,
            }
        
        production_data = read_production_csv(csv_path)
        
        if not production_data:
            errors.append("No production data found in CSV file")
            return {
                "response": "No production data available for analysis.",
                "errors": errors,
            }
        
        # ── Step 2: Calculate OEE for each row ───────────
        oee_results = []
        downtime_reasons = {}
        
        for row in production_data:
            result = calculate_oee(
                planned_minutes=row["planned_minutes"],
                actual_run_minutes=row["actual_run_minutes"],
                downtime_minutes=row["downtime_minutes"],
                ideal_cycle_time_seconds=row["ideal_cycle_time_seconds"],
                total_count=row["total_count"],
                good_count=row["good_count"],
            )
            # Attach date from CSV row for charting
            result.date = row["date"]
            oee_results.append(result)
            
            # Aggregate downtime by reason
            reason = row.get("downtime_reason", "unknown")
            if reason and reason != "none":
                downtime_reasons[reason] = downtime_reasons.get(reason, 0) + row["downtime_minutes"]
        
        # ── Step 3: Calculate average OEE ────────────────
        average_oee = calculate_average_oee(oee_results)
        
        # ── Step 4: Generate trend data (daily aggregation) ──
        dates = [row["date"] for row in production_data]
        
        daily_oee = defaultdict(list)
        daily_dates = []
        
        for i, (result, date) in enumerate(zip(oee_results, dates)):
            if date not in daily_oee:
                daily_oee[date] = []
                daily_dates.append(date)
            daily_oee[date].append(result.oee)
        
        daily_avg_oee = [
            sum(scores) / len(scores) for scores in daily_oee.values()
        ]
        
        # Build daily results for chart
        daily_results = []
        for date, avg_oee_score in zip(daily_dates, daily_avg_oee):
            # Find first result for this date
            first_for_date = next(r for r in oee_results if r.date == date)
            daily_results.append(first_for_date)
        
        # ── Step 5: Generate charts ──────────────────────
        chart_paths = []
        
        trend_chart = create_oee_trend_chart(daily_results, daily_dates, "OEE Trend Analysis")
        if trend_chart:
            chart_paths.append(trend_chart)
        
        downtime_chart = create_downtime_pie_chart(downtime_reasons, "Downtime Breakdown")
        if downtime_chart:
            chart_paths.append(downtime_chart)
        
        # ── Step 6: Build response ───────────────────────
        response = _generate_oee_response(average_oee, oee_results, downtime_reasons)
        
        return {
            "response": response,
            "intent": "oee",
            "attachments": chart_paths,
            "metadata": {
                **metadata,
                "oee_score": average_oee.oee,
                "oee_rating": average_oee.rating,
                "data_points": len(oee_results),
                "date_range": f"{production_data[0]['date']} to {production_data[-1]['date']}",
            },
        }
    
    except FileNotFoundError as e:
        errors.append(str(e))
        return {"response": "Error: Production data file not found.", "errors": errors}
    
    except Exception as e:
        errors.append(f"OEE analysis failed: {str(e)}")
        return {"response": "OEE analysis encountered an error.", "errors": errors}


def _generate_oee_response(
    average_oee,
    all_results: list,
    downtime_reasons: dict,
) -> str:
    """Generate human-readable OEE analysis response."""
    
    # Get date range from CSV rows (not from OEEResult which has no date field)
    date_range = "N/A"
    if all_results:
        try:
            date_range = f"{all_results[0].date} to {all_results[-1].date}"
        except AttributeError:
            date_range = "N/A"
    
    response = f"**OEE Analysis Report**\n"
    response += f"{'=' * 50}\n"
    response += f"Date Range: {date_range}\n"
    response += f"Total Shifts Analyzed: {len(all_results)}\n"
    response += f"\n"
    response += f"**Overall OEE Score: {average_oee.oee:.1f}%**\n"
    response += f"Rating: {average_oee.rating.replace('_', ' ').title()}\n"
    response += f"\n"
    response += f"**Components:**\n"
    response += f"  • Availability: {average_oee.availability:.1f}%\n"
    response += f"  • Performance:  {average_oee.performance:.1f}%\n"
    response += f"  • Quality:      {average_oee.quality:.1f}%\n"
    response += f"\n"
    response += f"**Total Production:**\n"
    response += f"  • Total Units:  {average_oee.total_count:,}\n"
    response += f"  • Good Units:   {average_oee.good_count:,}\n"
    response += f"  • Defects:      {average_oee.defect_count:,} ({(1 - average_oee.quality/100)*100:.1f}%)\n"
    response += f"\n"
    response += f"**Recommendation:** {average_oee.recommendation}\n"
    
    if downtime_reasons:
        response += f"\n**Top Downtime Causes:**\n"
        sorted_reasons = sorted(downtime_reasons.items(), key=lambda x: x[1], reverse=True)
        for reason, minutes in sorted_reasons[:3]:
            response += f"  • {reason}: {minutes:.0f} minutes\n"
    
    return response
