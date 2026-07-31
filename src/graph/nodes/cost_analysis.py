"""
Cost Analysis Node — Estimate scrap, rework, and waste costs.

Phase 4: Uses the CostEstimator engine for waste cost calculation
with Pareto ranking and ROI projections.
"""

from collections import defaultdict
from typing import Optional

from ..state import GodinezState
from ...tools.csv_reader import read_production_csv, filter_by_machine
from ...tools.analysis.cost_estimator import CostEstimator
from ...config import DATA_DIR


def cost_node(state: GodinezState) -> GodinezState:
    """
    Cost analysis node — reads CSV, estimates waste costs, returns breakdown.

    Uses the CostEstimator engine for cost analysis with Pareto ranking
    and ROI projections.

    Args:
        state: Current workflow state

    Returns:
        Updated state with cost findings in metadata and response
    """
    errors = state.get("errors", [])
    entities = state.get("entities", {})
    target_machine = entities.get("machine_id") or None

    try:
        csv_path = DATA_DIR / "sample_production.csv"
        if not csv_path.exists():
            errors.append(f"Cost data CSV not found: {csv_path}")
            return {
                "response": "Production data CSV not found for cost analysis.",
                "errors": errors,
            }

        production_data = read_production_csv(csv_path)
        if not production_data:
            errors.append("No production data for cost analysis")
            return {
                "response": "No production data available for cost analysis.",
                "errors": errors,
            }

        if target_machine:
            production_data = filter_by_machine(production_data, target_machine)

        # ── Use CostEstimator engine ───────────────────────────
        analysis = CostEstimator.analyze(production_data)

        # ── Build response ─────────────────────────────────────
        response = f"**Cost Analysis Report**\n{'=' * 50}\n"
        response += f"Data Points: {analysis.data_points}\n"
        response += f"Total Waste Cost: ${analysis.total_waste_cost:,.2f}\n\n"

        response += f"**Breakdown:**\n"
        for b in analysis.breakdown:
            response += f"  • {b.category.capitalize():12} {b.amount:>10.2f} {b.unit} @ ${b.rate:.2f}/{b.unit} = ${b.total:,.2f}\n"

        if analysis.waste_pareto:
            response += f"\n**Pareto (sorted by impact):**\n"
            running_total = 0
            for i, b in enumerate(analysis.waste_pareto, 1):
                running_total += b.total
                pct_of_total = (b.total / analysis.total_waste_cost * 100) if analysis.total_waste_cost > 0 else 0
                cumulative_pct = (running_total / analysis.total_waste_cost * 100) if analysis.total_waste_cost > 0 else 0
                response += f"  {i}. {b.category.capitalize()} — ${b.total:,.2f} ({pct_of_total:.1f}% of waste, {cumulative_pct:.1f}% cumulative)\n"

        if analysis.roi_projections:
            response += f"\n**ROI Projections:**\n"
            for proj in analysis.roi_projections:
                response += f"\n  💡 {proj['suggestion']}\n"
                response += f"     Annual savings: ${proj['annual_savings']:,.2f}"
                response += f" | Investment: ${proj['investment']:,.2f}"
                response += f" | Payback: {proj['payback_months']} months\n"

        # Extract flat cost values from breakdown for backward compat
        cost_by_category = {b.category.lower(): b.total for b in analysis.breakdown}
        scrap_cost = cost_by_category.get("scrap", 0.0)
        downtime_cost = cost_by_category.get("downtime", 0.0)
        quality_loss = cost_by_category.get("quality loss", 0.0)

        return {
            **state,
            "response": response,
            "analysis_results": {
                **state.get("analysis_results", {}),
                "cost": {
                    "total_waste_cost": round(analysis.total_waste_cost, 2),
                    "scrap_cost": round(scrap_cost, 2),
                    "rework_cost": round(quality_loss, 2),  # maps from quality loss
                    "downtime_cost": round(downtime_cost, 2),
                    "breakdown": [b.to_dict() for b in analysis.breakdown],
                    "waste_pareto": [b.to_dict() for b in analysis.waste_pareto],
                    "roi_projections": analysis.roi_projections,
                    "data_points": analysis.data_points,
                },
            },
            "errors": errors,
            "metadata": {
                **state.get("metadata", {}),
                "cost_analysis": True,
                "total_waste_cost": round(analysis.total_waste_cost, 2),
            },
        }

    except Exception as e:
        errors.append(f"Cost analysis failed: {e}")
        return {
            **state,
            "response": f"⚠️ Cost analysis encountered an error: {e}",
            "errors": errors,
        }
