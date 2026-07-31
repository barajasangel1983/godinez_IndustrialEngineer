"""
Bottleneck Detector — Identify production constraints and line imbalances.

Phase 4: Determines the constraint station using Theory of Constraints principles.
"""

from dataclasses import dataclass, field
from typing import Optional

from src.config import config as _cfg


@dataclass
class BottleneckResult:
    """Structured result from bottleneck detection."""
    line_name: str = ""
    overall_severity: str = "low"  # critical | high | medium | low
    balance_delay_pct: float = 0.0
    theoretical_balance_efficiency_pct: float = 0.0
    constraint_station: str = ""
    constraint_utilization_pct: float = 0.0
    top_findings: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    data_points: int = 0

    def to_dict(self) -> dict:
        """Serialize to dict for API/state serialization."""
        return {
            "line_name": self.line_name,
            "overall_severity": self.overall_severity,
            "balance_delay_pct": round(self.balance_delay_pct, 2),
            "theoretical_balance_efficiency_pct": round(self.theoretical_balance_efficiency_pct, 2),
            "constraint_station": self.constraint_station,
            "constraint_utilization_pct": round(self.constraint_utilization_pct, 2),
            "top_findings": self.top_findings,
            "suggestions": self.suggestions,
            "data_points": self.data_points,
        }


class BottleneckDetector:
    """Detect production bottlenecks using cycle time and utilization analysis."""

    # Severity thresholds for balance delay (%) — loaded from config at startup
    SEVERITY_THRESHOLDS = {
        "critical": _cfg.bottleneck.severity_critical,
        "high": _cfg.bottleneck.severity_high,
        "medium": _cfg.bottleneck.severity_medium,
        "low": 0,
    }

    # ToC improvement suggestion templates
    SUGGESTION_TEMPLATES = {
        "exploit": [
            "Reduce setup time on {station} by standardizing changeover procedures",
            "Eliminate non-value-added motion on {station}",
            "Pre-stage materials at {station} to reduce wait time",
        ],
        "subordinate": [
            "Pace upstream stations to match {station}'s cycle time",
            "Add buffer inventory before {station} to prevent starvation",
            "Redirect operators from non-constraint to support {station} during peaks",
        ],
        "elevate": [
            "Add a second shift on {station} to increase capacity",
            "Invest in automation to reduce {station}'s cycle time",
            "Outsource overflow work to relieve {station} constraint",
        ],
    }

    @classmethod
    def analyze(
        cls,
        data: list[dict],
        station_column: str = "machine_id",
        cycle_time_column: str = "ideal_cycle_time_seconds",
        utilization_column: str = "actual_run_minutes",
        planned_column: str = "planned_minutes",
    ) -> BottleneckResult:
        """
        Analyze production data to identify bottlenecks.

        Args:
            data: List of production records (rows from CSV)
            station_column: Column name for station/machine ID
            cycle_time_column: Column name for ideal cycle time
            utilization_column: Column name for actual run minutes
            planned_column: Column name for planned minutes

        Returns:
            BottleneckResult with findings
        """
        if not data:
            return BottleneckResult(data_points=0)

        # Group data by station
        stations = {}
        for row in data:
            station = row.get(station_column, "unknown")
            if station not in stations:
                stations[station] = []
            stations[station].append(row)

        # Calculate per-station metrics
        station_metrics = []
        for station, rows in stations.items():
            avg_ct = sum(r.get(cycle_time_column, 0) for r in rows) / len(rows)
            total_run = sum(r.get(utilization_column, 0) for r in rows)
            total_planned = sum(r.get(planned_column, 0) for r in rows)
            utilization = (total_run / total_planned * 100) if total_planned > 0 else 0
            station_metrics.append({
                "station": station,
                "avg_cycle_time": avg_ct,
                "utilization": utilization,
                "record_count": len(rows),
            })

        if len(station_metrics) < 2:
            return BottleneckResult(
                data_points=len(data),
                overall_severity="low",
                suggestions=["Need data from at least 2 stations for bottleneck analysis"],
            )

        # Find constraint (highest cycle time = true bottleneck)
        constraint = max(station_metrics, key=lambda s: s["avg_cycle_time"])

        # Calculate line balance metrics
        cycle_times = [s["avg_cycle_time"] for s in station_metrics]
        max_ct = max(cycle_times)
        avg_ct = sum(cycle_times) / len(cycle_times)
        balance_delay = ((max_ct - avg_ct) / max_ct * 100) if max_ct > 0 else 0
        tbe = ((len(cycle_times) * avg_ct) / (len(cycle_times) * max_ct) * 100) if max_ct > 0 else 100

        # Determine severity
        severity = cls._get_severity(balance_delay)

        # Build findings list
        findings = []
        for sm in station_metrics:
            score = sm["avg_cycle_time"]  # Score by cycle time (higher = worse)
            findings.append({
                "station": sm["station"],
                "metric_name": "avg_cycle_time",
                "value": round(sm["avg_cycle_time"], 2),
                "unit": "seconds",
                "severity": severity,
                "score": round(score, 2),
                "recommendation": f"Station {sm['station']} has highest cycle time at {sm['avg_cycle_time']:.1f}s",
            })

        # Build ToC suggestions
        suggestions = []
        suggestions.extend(cls.SUGGESTION_TEMPLATES["exploit"][:2])
        suggestions.extend(cls.SUGGESTION_TEMPLATES["subordinate"][:1])

        return BottleneckResult(
            line_name="Line-1",  # Could be derived from data
            overall_severity=severity,
            balance_delay_pct=balance_delay,
            theoretical_balance_efficiency_pct=tbe,
            constraint_station=constraint["station"],
            constraint_utilization_pct=constraint["utilization"],
            top_findings=findings,
            suggestions=suggestions,
            data_points=len(data),
        )

    @classmethod
    def _get_severity(cls, balance_delay_pct: float) -> str:
        """Map balance delay to severity level."""
        if balance_delay_pct >= cls.SEVERITY_THRESHOLDS["critical"]:
            return "critical"
        elif balance_delay_pct >= cls.SEVERITY_THRESHOLDS["high"]:
            return "high"
        elif balance_delay_pct >= cls.SEVERITY_THRESHOLDS["medium"]:
            return "medium"
        else:
            return "low"
