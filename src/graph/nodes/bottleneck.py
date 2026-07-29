"""
Bottleneck Detection Node — Identify production constraints and throughput limits.

Phase 2: Detect bottlenecks by analyzing:
- Cycle time variance (highest variance = most unstable process)
- Downtime concentration (longest downtime per machine)
- Capacity utilization (machine running closest to 100%)
- Throughput ranking (lowest output machines)

Uses deterministic calculation from production CSV data.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..state import GodinezState
from ...tools.csv_reader import read_production_csv, filter_by_date, filter_by_machine
from ...tools.oee_calculator import calculate_oee, calculate_average_oee
from ...config import DATA_DIR


@dataclass
class BottleneckFinding:
    """A single bottleneck finding."""
    machine_id: str
    bottleneck_type: str  # "cycle_time_variance", "downtime", "capacity", "throughput"
    severity: str  # "critical", "warning", "info"
    metric: float
    unit: str
    description: str
    recommendation: str


@dataclass
class BottleneckResult:
    """Aggregated bottleneck analysis results."""
    findings: list[BottleneckFinding] = field(default_factory=list)
    total_bottlenecks: int = 0
    critical_count: int = 0
    bottleneck_type_breakdown: dict[str, int] = field(default_factory=dict)


def analyze_bottlenecks(
    production_data: list[dict],
    target_machine: Optional[str] = None,
) -> BottleneckResult:
    """
    Analyze production data for bottleneck patterns.

    Args:
        production_data: List of production log dicts from CSV reader
        target_machine: Optional machine_id to filter to

    Returns:
        BottleneckResult with findings and breakdown
    """
    if target_machine:
        production_data = filter_by_machine(production_data, target_machine)

    result = BottleneckResult()

    if not production_data:
        return result

    # ── Group by machine ───────────────────────────────────
    machine_data = defaultdict(list)
    for row in production_data:
        machine_data[row["machine_id"]].append(row)

    # ── Analysis per machine ───────────────────────────────
    for machine_id, shifts in machine_data.items():
        # 1. Cycle time variance (higher variance = more unstable)
        ideal_cycle_times = [s["ideal_cycle_time_seconds"] for s in shifts if s["ideal_cycle_time_seconds"] > 0]
        if ideal_cycle_times:
            avg_cycle = sum(ideal_cycle_times) / len(ideal_cycle_times)
            variance = sum((t - avg_cycle) ** 2 for t in ideal_cycle_times) / len(ideal_cycle_times)
            std_dev = variance ** 0.5

            if std_dev > avg_cycle * 0.15:  # >15% std dev
                severity = "critical" if std_dev > avg_cycle * 0.3 else "warning"
                result.findings.append(BottleneckFinding(
                    machine_id=machine_id,
                    bottleneck_type="cycle_time_variance",
                    severity=severity,
                    metric=round(std_dev, 2),
                    unit="seconds",
                    description=f"Cycle time std dev {std_dev:.1f}s ({std_dev/avg_cycle*100:.0f}% of avg {avg_cycle:.0f}s) — highly unstable",
                    recommendation="Investigate setup inconsistencies, material quality variations, or operator training gaps",
                ))
                result.bottleneck_type_breakdown["cycle_time_variance"] = result.bottleneck_type_breakdown.get("cycle_time_variance", 0) + 1

        # 2. Downtime concentration
        total_run = sum(s["actual_run_minutes"] or 0 for s in shifts)
        total_downtime = sum(s["downtime_minutes"] or 0 for s in shifts)
        downtime_pct = (total_downtime / total_run * 100) if total_run > 0 else 0

        if downtime_pct > 20:
            severity = "critical" if downtime_pct > 35 else "warning"
            result.findings.append(BottleneckFinding(
                machine_id=machine_id,
                bottleneck_type="downtime",
                severity=severity,
                metric=round(downtime_pct, 1),
                unit="%",
                description=f"Downtime {downtime_pct:.1f}% of run time ({total_downtime:.0f} min lost)",
                recommendation="Prioritize preventive maintenance and root-cause top 3 downtime reasons",
            ))
            result.bottleneck_type_breakdown["downtime"] = result.bottleneck_type_breakdown.get("downtime", 0) + 1

        # 3. Capacity utilization (approaching 100% = constraint)
        planned_minutes = sum(s["planned_minutes"] or 0 for s in shifts)
        planned_output = planned_minutes * 60 / avg_cycle if avg_cycle > 0 else 0
        actual_output = sum(s["total_count"] or 0 for s in shifts)
        utilization = (actual_output / planned_output * 100) if planned_output > 0 else 0

        if utilization > 90:
            severity = "critical" if utilization > 98 else "warning"
            result.findings.append(BottleneckFinding(
                machine_id=machine_id,
                bottleneck_type="capacity",
                severity=severity,
                metric=round(utilization, 1),
                unit="%",
                description=f"Capacity utilization {utilization:.1f}% — approaching maximum output",
                recommendation="Consider scheduling additional shifts or upgrading equipment to relieve constraint",
            ))
            result.bottleneck_type_breakdown["capacity"] = result.bottleneck_type_breakdown.get("capacity", 0) + 1

        # 4. Throughput ranking (lowest output machines are potential bottlenecks)
        avg_throughput = actual_output / len(shifts) if shifts else 0
        result.findings.append(BottleneckFinding(
            machine_id=machine_id,
            bottleneck_type="throughput",
            severity="info",
            metric=round(avg_throughput, 1),
            unit="units/shift",
            description=f"Average throughput {avg_throughput:.1f} units/shift",
            recommendation=f"{'Top performer — benchmark others against this' if avg_throughput > 100 else 'Review setup and process to improve output'},",
        ))
        result.bottleneck_type_breakdown["throughput"] = result.bottleneck_type_breakdown.get("throughput", 0) + 1

    # ── Sort by severity ───────────────────────────────────
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    result.findings.sort(key=lambda f: severity_order.get(f.severity, 3))

    result.total_bottlenecks = len(result.findings)
    result.critical_count = sum(1 for f in result.findings if f.severity == "critical")

    return result


def bottleneck_node(state: GodinezState) -> GodinezState:
    """
    Bottleneck analysis node — reads CSV, detects constraints, returns findings.

    Args:
        state: Current workflow state

    Returns:
        Updated state with bottleneck findings in metadata and response
    """
    errors = state.get("errors", [])
    entities = state.get("entities", {})
    target_machine = entities.get("machine_id") or None

    try:
        csv_path = DATA_DIR / "sample_production.csv"
        if not csv_path.exists():
            errors.append(f"Bottleneck data CSV not found: {csv_path}")
            return {
                "response": "Production data CSV not found for bottleneck analysis.",
                "errors": errors,
            }

        production_data = read_production_csv(csv_path)
        if not production_data:
            errors.append("No production data for bottleneck analysis")
            return {
                "response": "No production data available for bottleneck analysis.",
                "errors": errors,
            }

        analysis = analyze_bottlenecks(production_data, target_machine)

        # ── Build response ─────────────────────────────────
        if analysis.total_bottlenecks == 0:
            response = "✅ No significant bottlenecks detected.\n\nAll machines are operating within normal parameters."
        else:
            response = f"**Bottleneck Analysis Report**\n{'=' * 50}\n"
            response += f"Total Findings: {analysis.total_bottlenecks} ({analysis.critical_count} critical)\n\n"

            # Group by severity
            for severity in ["critical", "warning", "info"]:
                sev_findings = [f for f in analysis.findings if f.severity == severity]
                if not sev_findings:
                    continue

                severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}[severity]
                response += f"\n**{severity.title()}**\n"

                for f in sev_findings:
                    response += f"\n  {severity_icon} **{f.machine_id}** — {f.bottleneck_type}\n"
                    response += f"     {f.description}\n"
                    response += f"     💡 {f.recommendation}\n"

        return {
            **state,
            "response": response,
            "analysis_results": {
                **state.get("analysis_results", {}),
                "bottleneck": {
                    "total_bottlenecks": analysis.total_bottlenecks,
                    "critical_count": analysis.critical_count,
                    "bottleneck_type_breakdown": analysis.bottleneck_type_breakdown,
                    "findings_count": len(analysis.findings),
                },
            },
            "errors": errors if errors else None,
            "metadata": {
                **state.get("metadata", {}),
                "bottleneck_analysis": True,
                "total_findings": analysis.total_bottlenecks,
                "critical_findings": analysis.critical_count,
            },
        }

    except Exception as e:
        errors.append(f"Bottleneck analysis failed: {e}")
        return {
            **state,
            "response": f"⚠️ Bottleneck analysis encountered an error: {e}",
            "errors": errors,
        }
