"""
Bottleneck Detection Node — Identify production constraints and throughput limits.

Phase 4: Uses the BottleneckDetector engine for constraint identification
plus inline analysis for per-machine breakdown (cycle time variance,
downtime concentration, capacity utilization, throughput ranking).
"""

from collections import defaultdict
from typing import Optional

from ..state import GodinezState
from ...tools.csv_reader import read_production_csv, filter_by_machine
from ...tools.analysis.bottleneck_detector import BottleneckDetector
from ...config import DATA_DIR


def _per_machine_analysis(
    production_data: list[dict],
    target_machine: Optional[str] = None,
) -> dict:
    """
    Per-machine bottleneck analysis (cycle time variance, downtime,
    capacity, throughput). Returns a structured dict for the response.
    """
    if target_machine:
        production_data = filter_by_machine(production_data, target_machine)

    findings: list[dict] = []

    # Group by machine
    machine_data = defaultdict(list)
    for row in production_data:
        machine_data[row["machine_id"]].append(row)

    for machine_id, shifts in machine_data.items():
        # 1. Cycle time variance
        ideal_cycle_times = [s["ideal_cycle_time_seconds"] for s in shifts if s.get("ideal_cycle_time_seconds", 0) > 0]
        if ideal_cycle_times:
            avg_cycle = sum(ideal_cycle_times) / len(ideal_cycle_times)
            variance = sum((t - avg_cycle) ** 2 for t in ideal_cycle_times) / len(ideal_cycle_times)
            std_dev = variance ** 0.5

            if std_dev > avg_cycle * 0.15:
                severity = "critical" if std_dev > avg_cycle * 0.3 else "warning"
                findings.append({
                    "machine_id": machine_id,
                    "bottleneck_type": "cycle_time_variance",
                    "severity": severity,
                    "metric": round(std_dev, 2),
                    "unit": "seconds",
                    "description": f"Cycle time std dev {std_dev:.1f}s ({std_dev/avg_cycle*100:.0f}% of avg {avg_cycle:.0f}s) — highly unstable",
                    "recommendation": "Investigate setup inconsistencies, material quality variations, or operator training gaps",
                })

        # 2. Downtime concentration
        total_run = sum(s.get("actual_run_minutes", 0) or 0 for s in shifts)
        total_downtime = sum(s.get("downtime_minutes", 0) or 0 for s in shifts)
        downtime_pct = (total_downtime / total_run * 100) if total_run > 0 else 0

        if downtime_pct > 20:
            severity = "critical" if downtime_pct > 35 else "warning"
            findings.append({
                "machine_id": machine_id,
                "bottleneck_type": "downtime",
                "severity": severity,
                "metric": round(downtime_pct, 1),
                "unit": "%",
                "description": f"Downtime {downtime_pct:.1f}% of run time ({total_downtime:.0f} min lost)",
                "recommendation": "Prioritize preventive maintenance and root-cause top 3 downtime reasons",
            })

        # 3. Capacity utilization (approximate — uses avg cycle time)
        if ideal_cycle_times:
            avg_cycle = sum(ideal_cycle_times) / len(ideal_cycle_times)
            planned_minutes = sum(s.get("planned_minutes", 0) or 0 for s in shifts)
            planned_output = planned_minutes * 60 / avg_cycle if avg_cycle > 0 else 0
            actual_output = sum(s.get("total_count", 0) or 0 for s in shifts)
            utilization = (actual_output / planned_output * 100) if planned_output > 0 else 0

            if utilization > 90:
                severity = "critical" if utilization > 98 else "warning"
                findings.append({
                    "machine_id": machine_id,
                    "bottleneck_type": "capacity",
                    "severity": severity,
                    "metric": round(utilization, 1),
                    "unit": "%",
                    "description": f"Capacity utilization {utilization:.1f}% — approaching maximum output",
                    "recommendation": "Consider scheduling additional shifts or upgrading equipment to relieve constraint",
                })

        # 4. Throughput ranking (always reported at info level)
        avg_throughput = sum(s.get("total_count", 0) or 0 for s in shifts) / len(shifts) if shifts else 0
        findings.append({
            "machine_id": machine_id,
            "bottleneck_type": "throughput",
            "severity": "info",
            "metric": round(avg_throughput, 1),
            "unit": "units/shift",
            "description": f"Average throughput {avg_throughput:.1f} units/shift",
            "recommendation": f"{'Top performer — benchmark others against this' if avg_throughput > 100 else 'Review setup and process to improve output'}",
        })

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: severity_order.get(f["severity"], 3))

    return {
        "findings": findings,
        "total_bottlenecks": len(findings),
        "critical_count": sum(1 for f in findings if f["severity"] == "critical"),
        "bottleneck_type_breakdown": defaultdict(int),
    }


def bottleneck_node(state: GodinezState) -> GodinezState:
    """
    Bottleneck analysis node — reads CSV, detects constraints, returns findings.

    Uses the BottleneckDetector engine for constraint identification
    and inline per-machine analysis for detailed breakdown.

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

        # ── Use BottleneckDetector engine ────────────────────────
        detector_result = BottleneckDetector.analyze(production_data)
        constraint_info = {
            "constraint_station": detector_result.constraint_station,
            "overall_severity": detector_result.overall_severity,
            "balance_delay_pct": detector_result.balance_delay_pct,
            "constraint_utilization_pct": detector_result.constraint_utilization_pct,
        }

        # ── Inline per-machine analysis ──────────────────────────
        analysis = _per_machine_analysis(production_data, target_machine)
        findings = analysis["findings"]

        # ── Build response ──────────────────────────────────────
        if analysis["total_bottlenecks"] == 0:
            response = "✅ No significant bottlenecks detected.\n\nAll machines are operating within normal parameters."
        else:
            response = f"**Bottleneck Analysis Report**\n{'=' * 50}\n"
            response += f"Total Findings: {analysis['total_bottlenecks']} ({analysis['critical_count']} critical)\n"

            if detector_result.constraint_station:
                response += f"\n**Constraint Station:** {detector_result.constraint_station}"
                response += f" (utilization: {detector_result.constraint_utilization_pct:.1f}%)"
                response += f"\n**Balance Delay:** {detector_result.balance_delay_pct:.1f}% | Severity: {detector_result.overall_severity}"

            if detector_result.suggestions:
                response += "\n\n**Improvement Suggestions:**\n"
                for i, s in enumerate(detector_result.suggestions[:4], 1):
                    response += f"  {i}. {s}\n"

            # Group by severity
            for severity in ["critical", "warning", "info"]:
                sev_findings = [f for f in findings if f["severity"] == severity]
                if not sev_findings:
                    continue

                severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}[severity]
                response += f"\n**{severity.title()}**\n"

                for f in sev_findings:
                    response += f"\n  {severity_icon} **{f['machine_id']}** — {f['bottleneck_type']}\n"
                    response += f"     {f['description']}\n"
                    response += f"     💡 {f['recommendation']}\n"

        return {
            **state,
            "response": response,
            "analysis_results": {
                **state.get("analysis_results", {}),
                "bottleneck": {
                    "total_bottlenecks": analysis["total_bottlenecks"],
                    "critical_count": analysis["critical_count"],
                    "bottleneck_type_breakdown": dict(analysis["bottleneck_type_breakdown"]),
                    "findings_count": len(findings),
                    "constraint_info": constraint_info,
                },
            },
            "errors": errors,
            "metadata": {
                **state.get("metadata", {}),
                "bottleneck_analysis": True,
                "total_findings": analysis["total_bottlenecks"],
                "critical_findings": analysis["critical_count"],
            },
        }

    except Exception as e:
        errors.append(f"Bottleneck analysis failed: {e}")
        return {
            **state,
            "response": f"⚠️ Bottleneck analysis encountered an error: {e}",
            "errors": errors,
        }
