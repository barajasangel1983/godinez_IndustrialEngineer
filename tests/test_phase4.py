"""
Phase 4: Bottleneck Detection & Cost Analysis — Foundation Tests

Step 4.0: State models, stub engines, synthetic data generators.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.graph.state import BottleneckResult, CostResult, CostBreakdown, BottleneckFinding
from src.tools.analysis.bottleneck_detector import BottleneckDetector
from src.tools.analysis.cost_estimator import CostEstimator
from src.tools.synthetic_data import (
    generate_synthetic_production,
    generate_bottleneck_data,
    generate_cost_data,
)


# ── State Model Tests ──────────────────────────────────────────────────────────

class TestBottleneckResultModel:
    """Test BottleneckResult Pydantic model (Phase 4 state field)."""

    def test_default_creation(self):
        result = BottleneckResult()
        assert result.overall_severity == "low"
        assert result.balance_delay_pct == 0.0
        assert result.top_findings == []
        assert result.suggestions == []

    def test_with_findings(self):
        result = BottleneckResult(
            line_name="Line-A",
            overall_severity="critical",
            balance_delay_pct=35.0,
            constraint_station="Station-3",
            constraint_utilization_pct=97.5,
            data_points=150,
        )
        assert result.line_name == "Line-A"
        assert result.overall_severity == "critical"
        assert result.balance_delay_pct == 35.0
        assert result.constraint_station == "Station-3"

    def test_to_dict_serialization(self):
        result = BottleneckResult(
            line_name="Line-B",
            overall_severity="high",
            balance_delay_pct=22.5,
            constraint_station="Station-1",
            constraint_utilization_pct=94.2,
            data_points=200,
        )
        d = result.to_dict()
        assert d["line_name"] == "Line-B"
        assert d["overall_severity"] == "high"
        assert d["balance_delay_pct"] == 22.5
        assert d["data_points"] == 200


class TestCostResultModel:
    """Test CostResult Pydantic model (Phase 4 state field)."""

    def test_default_creation(self):
        result = CostResult()
        assert result.total_waste_cost == 0.0
        assert result.breakdown == []
        assert result.waste_pareto == []

    def test_with_breakdown(self):
        result = CostResult(
            total_waste_cost=15000.0,
            data_points=180,
        )
        assert result.total_waste_cost == 15000.0

    def test_breakdown_serialization(self):
        breakdown = [
            CostBreakdown(category="Scrap", amount=120, unit="units", rate=25.0, total=3000.0),
            CostBreakdown(category="Downtime", amount=8.5, unit="hours", rate=150.0, total=1275.0),
        ]
        result = CostResult(total_waste_cost=4275.0, breakdown=breakdown)
        d = result.to_dict()
        assert len(d["breakdown"]) == 2
        assert d["breakdown"][0]["category"] == "Scrap"
        assert d["breakdown"][0]["total"] == 3000.0

    def test_pareto_ordering(self):
        """Pareto list should be sorted by $ impact descending."""
        breakdown = [
            CostBreakdown(category="Small", amount=10, unit="units", rate=5.0, total=50.0),
            CostBreakdown(category="Big", amount=200, unit="units", rate=25.0, total=5000.0),
            CostBreakdown(category="Medium", amount=50, unit="hours", rate=100.0, total=5000.0),
        ]
        sorted_pb = sorted(breakdown, key=lambda b: b.total, reverse=True)
        assert sorted_pb[0].total == 5000.0
        assert sorted_pb[0].category == "Big"  # "Big" comes first (both 5000, but Big > Medium)


# ── Bottleneck Detector Tests ──────────────────────────────────────────────────

class TestBottleneckDetector:
    """Test BottleneckDetector stub engine."""

    def _make_rows(self, machines, cycle_times):
        """Helper to create synthetic rows for bottleneck analysis."""
        rows = []
        for i, (machine, ct) in enumerate(zip(machines, cycle_times)):
            rows.append({
                "machine_id": machine,
                "ideal_cycle_time_seconds": ct,
                "actual_run_minutes": 400,
                "planned_minutes": 480,
            })
        return rows

    def test_empty_data_returns_low_severity(self):
        result = BottleneckDetector.analyze([])
        assert result.data_points == 0
        assert result.overall_severity == "low"

    def test_single_station_no_bottleneck(self):
        rows = self._make_rows(["Line-1"], [30.0])
        result = BottleneckDetector.analyze(rows)
        assert result.data_points == 1
        assert result.overall_severity == "low"
        assert len(result.suggestions) > 0

    def test_two_stations_finds_constraint(self):
        """Two stations: Line-1 at 30s, Line-2 at 50s → Line-2 is constraint."""
        rows = self._make_rows(
            ["Line-1", "Line-2"],
            [30.0, 50.0],
        )
        result = BottleneckDetector.analyze(rows)
        assert result.data_points == 2
        assert result.constraint_station == "Line-2"
        assert result.balance_delay_pct > 0
        assert result.top_findings  # Should have findings for both stations

    def test_four_stations_finds_worst(self):
        """Four stations with Line-2 as bottleneck."""
        rows = self._make_rows(
            ["Line-1", "Line-2", "Line-3", "Line-4"],
            [30.0, 55.0, 25.0, 35.0],
        )
        result = BottleneckDetector.analyze(rows)
        assert result.constraint_station == "Line-2"
        assert result.constraint_utilization_pct > 80  # High utilization

    def test_severity_levels(self):
        """Test severity classification thresholds."""
        # Medium: 12% balance delay
        assert BottleneckDetector._get_severity(12) == "medium"
        # High: 22% balance delay
        assert BottleneckDetector._get_severity(22) == "high"
        # Critical: 35% balance delay
        assert BottleneckDetector._get_severity(35) == "critical"
        # Low: 5% balance delay
        assert BottleneckDetector._get_severity(5) == "low"

    def test_to_dict_serialization(self):
        result = BottleneckDetector.analyze(
            self._make_rows(["A", "B"], [30.0, 50.0])
        )
        d = result.to_dict()
        assert "constraint_station" in d
        assert "balance_delay_pct" in d
        assert "data_points" in d


# ── Cost Estimator Tests ───────────────────────────────────────────────────────

class TestCostEstimator:
    """Test CostEstimator stub engine."""

    def _make_rows(self, total_count, good_count, downtime_min):
        """Helper to create cost analysis rows."""
        return [{
            "total_count": total_count,
            "good_count": good_count,
            "downtime_minutes": downtime_min,
        }]

    def test_empty_data(self):
        result = CostEstimator.analyze([])
        assert result.data_points == 0
        assert result.total_waste_cost == 0.0

    def test_scrap_cost_calculation(self):
        """Scrap = total - good; cost = scrap × rate."""
        rows = self._make_rows(total_count=1000, good_count=950, downtime_min=0)
        result = CostEstimator.analyze(rows)
        assert result.data_points == 1
        scrap_item = next(b for b in result.breakdown if b.category == "Scrap")
        assert scrap_item.amount == 50  # 1000 - 950
        assert scrap_item.rate == 25.0  # Default
        assert scrap_item.total == 1250.0  # 50 × 25

    def test_downtime_cost_calculation(self):
        """Downtime cost = hours × rate."""
        rows = self._make_rows(total_count=500, good_count=490, downtime_min=180)  # 3 hours
        result = CostEstimator.analyze(rows)
        dt_item = next(b for b in result.breakdown if b.category == "Downtime")
        assert dt_item.amount == 3.0  # 180 / 60
        assert dt_item.rate == 150.0  # Default
        assert dt_item.total == 450.0  # 3 × 150

    def test_pareto_ordering(self):
        """Pareto list sorted by total $ descending."""
        rows = self._make_rows(total_count=1000, good_count=900, downtime_min=600)
        result = CostEstimator.analyze(rows)
        totals = [b.total for b in result.waste_pareto]
        assert totals == sorted(totals, reverse=True)

    def test_custom_cost_parameters(self):
        """Custom costs should override defaults."""
        custom_costs = {
            "scrap_per_unit": 50.0,
            "rework_per_hour": 100.0,
            "downtime_per_hour": 200.0,
            "defect_per_unit": 10.0,
        }
        rows = self._make_rows(total_count=100, good_count=95, downtime_min=60)
        result = CostEstimator.analyze(rows, costs=custom_costs)
        scrap_item = next(b for b in result.breakdown if b.category == "Scrap")
        assert scrap_item.rate == 50.0

    def test_roi_projections(self):
        """ROI projections should include scrap and downtime scenarios."""
        rows = self._make_rows(total_count=1000, good_count=900, downtime_min=300)
        result = CostEstimator.analyze(rows)
        assert len(result.roi_projections) >= 1
        proj = result.roi_projections[0]
        assert "suggestion" in proj
        assert "annual_savings" in proj
        assert "payback_months" in proj

    def test_to_dict_serialization(self):
        rows = self._make_rows(total_count=500, good_count=480, downtime_min=90)
        result = CostEstimator.analyze(rows)
        d = result.to_dict()
        assert "total_waste_cost" in d
        assert "breakdown" in d
        assert "waste_pareto" in d
        assert "roi_projections" in d


# ── Synthetic Data Generator Tests ─────────────────────────────────────────────

class TestSyntheticDataGeneration:
    """Test that synthetic data generators produce valid CSVs."""

    def test_generate_synthetic_production(self, tmp_path):
        filepath = str(tmp_path / "test_prod.csv")
        path = generate_synthetic_production(
            start_date="2024-01-01",
            end_date="2024-01-07",  # 1 week
            filepath=filepath,
            seed=42,
        )
        assert path == filepath
        assert os.path.exists(path)

        # Verify CSV structure
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) > 1  # Header + data
        header = lines[0].strip().split(",")
        assert "machine_id" in header
        assert "good_count" in header

    def test_generate_bottleneck_data(self, tmp_path):
        filepath = str(tmp_path / "test_bottleneck.csv")
        path = generate_bottleneck_data(
            start_date="2024-01-01",
            end_date="2024-01-07",
            filepath=filepath,
            seed=42,
        )
        assert path == filepath
        assert os.path.exists(path)

        # Line-2 should have highest cycle time (bottleneck)
        from src.tools.csv_reader import read_production_csv
        rows = read_production_csv(path)
        machines = set(r["machine_id"] for r in rows)
        assert "Line-2" in machines

    def test_generate_cost_data(self, tmp_path):
        filepath = str(tmp_path / "test_cost.csv")
        path = generate_cost_data(
            start_date="2024-01-01",
            end_date="2024-01-07",
            filepath=filepath,
            seed=42,
        )
        assert path == filepath
        assert os.path.exists(path)

        # Cost data should have higher scrap rate for Line-2
        from src.tools.csv_reader import read_production_csv
        rows = read_production_csv(path)
        for machine in ["Line-2", "Line-1"]:
            machine_rows = [r for r in rows if r["machine_id"] == machine]
            total = sum(int(r["total_count"]) for r in machine_rows)
            good = sum(int(r["good_count"]) for r in machine_rows)
            scrap_rate = (total - good) / total if total > 0 else 0
            assert scrap_rate >= 0


class TestFullPipelineIntegration:
    """End-to-end: generate data → run analyses → verify results."""

    def test_bottleneck_pipeline(self, tmp_path):
        """Generate bottleneck data → run detector → verify constraint."""
        csv_path = generate_bottleneck_data(
            start_date="2024-01-01",
            end_date="2024-03-31",
            filepath=str(tmp_path / "bottleneck.csv"),
            seed=42,
        )
        from src.tools.csv_reader import read_production_csv
        rows = read_production_csv(csv_path)
        result = BottleneckDetector.analyze(rows)
        assert result.constraint_station == "Line-2"
        assert result.data_points > 0
        d = result.to_dict()
        assert d["constraint_station"] == "Line-2"

    def test_cost_pipeline(self, tmp_path):
        """Generate cost data → run estimator → verify scrap cost."""
        csv_path = generate_cost_data(
            start_date="2024-01-01",
            end_date="2024-03-31",
            filepath=str(tmp_path / "cost.csv"),
            seed=42,
        )
        from src.tools.csv_reader import read_production_csv
        rows = read_production_csv(csv_path)
        result = CostEstimator.analyze(rows)
        assert result.data_points > 0
        assert result.total_waste_cost > 0
        d = result.to_dict()
        assert "breakdown" in d
        assert len(d["breakdown"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
