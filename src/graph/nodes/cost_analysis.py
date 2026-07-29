"""
Cost Analysis Node — Estimate scrap, rework, and waste costs.

Phase 2: Quantify waste by analyzing:
- Scrap rate and cost (defective units × unit cost)
- Rework cost (estimated based on rework time)
- Downtime cost (lost production value)
- Waste Pareto ranking (top cost drivers)

Uses deterministic calculation from production CSV data.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..state import GodinezState
from ...tools.csv_reader import read_production_csv, filter_by_machine
from ...config import DATA_DIR

# ── Default cost parameters (configurable via environment) ──────────────
DEFAULT_UNIT_COST = 15.00  # Average cost per unit ($15 for demo)
DEFAULT_REWORK_COST_PER_MINUTE = 0.50  # Labor + materials for rework
DEFAULT_DOWNTIME_COST_PER_MINUTE = 25.00  # Lost production during downtime


@dataclass
class CostFinding:
    """A single cost finding."""
    category: str  # "scrap", "rework", "downtime", "setup"
    amount: float  # Cost in dollars
    percentage: float  # Percentage of total waste
    description: str
    recommendation: str


@dataclass
class CostResult:
    """Aggregated cost analysis results."""
    findings: list[CostFinding] = field(default_factory=list)
    total_waste_cost: float = 0.0
    scrap_cost: float = 0.0
    rework_cost: float = 0.0
    downtime_cost: float = 0.0
    total_production_value: float = 0.0
    waste_percentage: float = 0.0


def analyze_costs(
    production_data: list[dict],
    unit_cost: float = DEFAULT_UNIT_COST,
    rework_cost_per_minute: float = DEFAULT_REWORK_COST_PER_MINUTE,
    downtime_cost_per_minute: float = DEFAULT_DOWNTIME_COST_PER_MINUTE,
    target_machine: Optional[str] = None,
) -> CostResult:
    """
    Analyze production data for cost metrics.

    Args:
        production_data: List of production log dicts from CSV reader
        unit_cost: Average cost per unit
        rework_cost_per_minute: Cost per minute of rework labor
        downtime_cost_per_minute: Cost per minute of lost production
        target_machine: Optional machine_id to filter to

    Returns:
        CostResult with findings and breakdown
    """
    if target_machine:
        production_data = filter_by_machine(production_data, target_machine)

    result = CostResult()

    if not production_data:
        return result

    # ── Aggregate totals ───────────────────────────────────
    total_units = sum(s["total_count"] or 0 for s in production_data)
    good_units = sum(s["good_count"] or 0 for s in production_data)
    total_downtime = sum(s["downtime_minutes"] or 0 for s in production_data)

    defective_units = total_units - good_units
    scrap_rate = (defective_units / total_units * 100) if total_units > 0 else 0

    # ── Cost calculations ──────────────────────────────────
    result.scrap_cost = defective_units * unit_cost
    result.rework_cost = defective_units * rework_cost_per_minute  # Estimate: 1 min per defect
    result.downtime_cost = total_downtime * downtime_cost_per_minute
    result.total_production_value = total_units * unit_cost

    result.total_waste_cost = result.scrap_cost + result.rework_cost + result.downtime_cost
    result.waste_percentage = (result.total_waste_cost / result.total_production_value * 100) if result.total_production_value > 0 else 0

    # ── Cost findings ──────────────────────────────────────
    if result.scrap_cost > 0:
        pct = (result.scrap_cost / result.total_waste_cost * 100) if result.total_waste_cost > 0 else 100
        result.findings.append(CostFinding(
            category="scrap",
            amount=round(result.scrap_cost, 2),
            percentage=round(pct, 1),
            description=f"Scrap: {defective_units} defective units × ${unit_cost:.2f} = ${result.scrap_cost:.2f}",
            recommendation=f"Target scrap rate below {max(1, scrap_rate - 1):.1f}% through process improvement and better QC",
        ))

    if result.rework_cost > 0:
        pct = (result.rework_cost / result.total_waste_cost * 100) if result.total_waste_cost > 0 else 100
        result.findings.append(CostFinding(
            category="rework",
            amount=round(result.rework_cost, 2),
            percentage=round(pct, 1),
            description=f"Rework: {defective_units} units × ${rework_cost_per_minute:.2f}/min ≈ ${result.rework_cost:.2f}",
            recommendation="Reduce rework by fixing root causes at first opportunity — don't wait for end-of-line defects",
        ))

    if result.downtime_cost > 0:
        pct = (result.downtime_cost / result.total_waste_cost * 100) if result.total_waste_cost > 0 else 100
        result.findings.append(CostFinding(
            category="downtime",
            amount=round(result.downtime_cost, 2),
            percentage=round(pct, 1),
            description=f"Downtime: {total_downtime:.0f} min × ${downtime_cost_per_minute:.2f}/min = ${result.downtime_cost:.2f}",
            recommendation="Implement predictive maintenance and reduce changeover times to minimize lost production",
        ))

    # Sort by cost (descending)
    result.findings.sort(key=lambda f: f.amount, reverse=True)

    return result


def cost_node(state: GodinezState) -> GodinezState:
    """
    Cost analysis node — reads CSV, estimates waste costs, returns breakdown.

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

        analysis = analyze_costs(production_data, target_machine=target_machine)

        # ── Build response ─────────────────────────────────
        response = f"**Cost Analysis Report**\n{'=' * 50}\n"
        response += f"Total Production Value: ${analysis.total_production_value:,.2f}\n"
        response += f"Total Waste Cost: ${analysis.total_waste_cost:,.2f} "
        response += f"({analysis.waste_percentage:.1f}% of production value)\n\n"

        response += f"**Breakdown:**\n"
        response += f"  • Scrap:      ${analysis.scrap_cost:>10,.2f}\n"
        response += f"  • Rework:     ${analysis.rework_cost:>10,.2f}\n"
        response += f"  • Downtime:   ${analysis.downtime_cost:>10,.2f}\n"

        if analysis.findings:
            response += f"\n\n**Top Cost Drivers:**\n"
            for i, f in enumerate(analysis.findings, 1):
                response += f"\n  {i}. **{f.category.upper()}** — ${f.amount:,.2f} ({f.percentage:.1f}%)\n"
                response += f"     {f.description}\n"
                response += f"     💡 {f.recommendation}\n"

        return {
            **state,
            "response": response,
            "analysis_results": {
                **state.get("analysis_results", {}),
                "cost": {
                    "total_waste_cost": round(analysis.total_waste_cost, 2),
                    "waste_percentage": round(analysis.waste_percentage, 2),
                    "scrap_cost": round(analysis.scrap_cost, 2),
                    "rework_cost": round(analysis.rework_cost, 2),
                    "downtime_cost": round(analysis.downtime_cost, 2),
                    "total_production_value": round(analysis.total_production_value, 2),
                },
            },
            "errors": errors if errors else None,
            "metadata": {
                **state.get("metadata", {}),
                "cost_analysis": True,
                "total_waste_cost": round(analysis.total_waste_cost, 2),
                "waste_percentage": round(analysis.waste_percentage, 2),
            },
        }

    except Exception as e:
        errors.append(f"Cost analysis failed: {e}")
        return {
            **state,
            "response": f"⚠️ Cost analysis encountered an error: {e}",
            "errors": errors,
        }
