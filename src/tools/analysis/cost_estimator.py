"""
Cost Estimator — Quantify waste and calculate ROI for improvements.

Phase 4: Scrap, rework, and downtime cost analysis with Pareto ranking.
"""

from dataclasses import dataclass, field
from typing import Optional

from src.config import config as _cfg


@dataclass
class CostBreakdown:
    """A single cost category."""
    category: str
    amount: float
    unit: str
    rate: float
    total: float

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "amount": round(self.amount, 2),
            "unit": self.unit,
            "rate": round(self.rate, 2),
            "total": round(self.total, 2),
        }


@dataclass
class CostResult:
    """Structured result from cost estimation."""
    total_waste_cost: float = 0.0
    breakdown: list = field(default_factory=list)
    waste_pareto: list = field(default_factory=list)
    roi_projections: list = field(default_factory=list)
    data_points: int = 0

    def to_dict(self) -> dict:
        return {
            "total_waste_cost": round(self.total_waste_cost, 2),
            "breakdown": [b.to_dict() for b in self.breakdown],
            "waste_pareto": [b.to_dict() for b in self.waste_pareto],
            "roi_projections": self.roi_projections,
            "data_points": self.data_points,
        }


class CostEstimator:
    """Estimate costs of scrap, rework, and downtime."""

    # Default cost parameters — loaded from config at startup
    DEFAULT_COSTS = {
        "scrap_per_unit": _cfg.cost.scrap_per_unit,
        "rework_per_hour": _cfg.cost.rework_per_hour,
        "downtime_per_hour": _cfg.cost.downtime_per_hour,
        "defect_per_unit": _cfg.cost.defect_per_unit,
    }

    @classmethod
    def analyze(
        cls,
        data: list[dict],
        costs: Optional[dict] = None,
        scrap_column: str = "total_count",
        good_count_column: str = "good_count",
        downtime_column: str = "downtime_minutes",
    ) -> CostResult:
        """
        Analyze production data to estimate waste costs.

        Args:
            data: List of production records
            costs: Custom cost parameters (overrides defaults)
            scrap_column: Column for total production count
            good_count_column: Column for good units produced
            downtime_column: Column for downtime minutes

        Returns:
            CostResult with breakdown and projections
        """
        costs = costs or cls.DEFAULT_COSTS
        if not data:
            return CostResult(data_points=0)

        # Aggregate metrics
        total_produced = sum(r.get(scrap_column, 0) for r in data)
        total_good = sum(r.get(good_count_column, 0) for r in data)
        total_downtime_min = sum(r.get(downtime_column, 0) for r in data)

        total_scrap = total_produced - total_good
        total_downtime_hours = total_downtime_min / 60 if total_downtime_min > 0 else 0

        # Build breakdown
        breakdown = []

        # Scrap cost
        scrap_total = total_scrap * costs["scrap_per_unit"]
        breakdown.append(CostBreakdown(
            category="Scrap",
            amount=total_scrap,
            unit="units",
            rate=costs["scrap_per_unit"],
            total=scrap_total,
        ))

        # Downtime cost
        downtime_total = total_downtime_hours * costs["downtime_per_hour"]
        breakdown.append(CostBreakdown(
            category="Downtime",
            amount=total_downtime_hours,
            unit="hours",
            rate=costs["downtime_per_hour"],
            total=downtime_total,
        ))

        # Defect/quality loss (scrap as percentage of revenue proxy)
        defect_rate = (total_scrap / total_produced * 100) if total_produced > 0 else 0
        quality_loss = total_scrap * costs["defect_per_unit"]
        breakdown.append(CostBreakdown(
            category="Quality Loss",
            amount=total_scrap,
            unit="units",
            rate=costs["defect_per_unit"],
            total=quality_loss,
        ))

        total_waste = sum(b.total for b in breakdown)

        # Pareto ranking (sorted by $ impact, descending)
        waste_pareto = sorted(breakdown, key=lambda b: b.total, reverse=True)

        # ROI projections
        roi_projections = cls._calculate_roi(
            breakdown, costs, total_produced, total_scrap
        )

        return CostResult(
            total_waste_cost=total_waste,
            breakdown=breakdown,
            waste_pareto=waste_pareto,
            roi_projections=roi_projections,
            data_points=len(data),
        )

    @classmethod
    def _calculate_roi(
        cls,
        breakdown: list[CostBreakdown],
        costs: dict,
        total_produced: int,
        total_scrap: int,
    ) -> list[dict]:
        """Calculate ROI projections for potential improvements."""
        projections = []

        if total_scrap > 0:
            # Scenario: 50% scrap reduction
            savings = total_scrap * 0.5 * costs["scrap_per_unit"]
            projections.append({
                "suggestion": "Reduce scrap rate by 50% through improved QC",
                "annual_savings": round(savings * 260, 2),  # Annualized (business days)
                "investment": 15000.0,
                "payback_months": 1 if savings * 260 >= 15000 else round(15000 / (savings * 260 / 12), 1),
            })

        downtime_item = next((b for b in breakdown if b.category == "Downtime"), None)
        if downtime_item and downtime_item.total > 0:
            # Scenario: 30% downtime reduction
            savings = downtime_item.total * 0.3
            projections.append({
                "suggestion": "Reduce downtime by 30% through preventive maintenance",
                "annual_savings": round(savings * 260, 2),
                "investment": 25000.0,
                "payback_months": 1 if savings * 260 >= 25000 else round(25000 / (savings * 260 / 12), 1),
            })

        return projections
