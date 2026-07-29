"""
Trend Engine & Trend Analysis Node Tests

Phase 3: Statistical trend analysis with forecasting, anomaly detection,
and visualization.
"""

import pytest
import numpy as np
from src.tools.analysis.trend_engine import TrendEngine, TrendResult, AnomalyResult
from src.graph.nodes.trend_analysis import trend_analysis_node, _calc_per_period_oee
from src.graph.nodes.analyze import analyze_node
from src.graph.nodes.response import response_node
from src.tools.synthetic_data import generate_synthetic_production


class TestTrendEngine:
    """Test the trend analysis engine."""
    
    def setup_method(self):
        """Create synthetic data and engine instance."""
        self.csv_path = generate_synthetic_production(
            start_date="2024-01-01",
            end_date="2024-06-30",
            seed=42,
        )
    
    def test_linear_regression_upward(self):
        """Test linear regression detects upward trend."""
        values = [10 + i * 2 for i in range(10)]
        slope, intercept, r_squared = TrendEngine._linear_regression(values)
        
        assert slope > 0
        assert r_squared > 0.99
        assert abs(slope - 2.0) < 0.01
    
    def test_linear_regression_downward(self):
        """Test linear regression detects downward trend."""
        values = [100 - i * 3 for i in range(10)]
        slope, intercept, r_squared = TrendEngine._linear_regression(values)
        
        assert slope < 0
        assert r_squared > 0.99
    
    def test_linear_regression_flat(self):
        """Test linear regression handles flat values."""
        values = [50.0] * 10
        slope, intercept, r_squared = TrendEngine._linear_regression(values)
        
        assert abs(slope) < 0.01
        assert abs(intercept - 50.0) < 0.01
    
    def test_analyze_trend(self):
        """Test trend analysis produces correct TrendResult."""
        values = [80 + i * 0.5 + np.random.normal(0, 0.5) for i in range(30)]
        result = TrendEngine.analyze_trend(values, "OEE")
        
        assert isinstance(result, TrendResult)
        assert result.series_name == "OEE"
        assert result.direction in ("up", "down", "stable")
        assert 0 <= result.r_squared <= 1
        assert result.forecast_7d >= 0
        assert result.forecast_30d >= 0
    
    def test_analyze_trend_insufficient_data(self):
        """Test trend with too few data points."""
        result = TrendEngine.analyze_trend([10], "single")
        
        assert result.direction == "stable"
        assert result.slope == 0.0
        assert result.r_squared == 0.0
    
    def test_detect_anomalies(self):
        """Test anomaly detection identifies outliers."""
        values = [10] * 20 + [100] + [10] * 10  # spike at index 20
        dates = [f"2024-01-{i:02d}" for i in range(31)]
        
        anomalies = TrendEngine.detect_anomalies(values, dates)
        
        assert len(anomalies) > 0
        # The spike should be detected
        spike_anomaly = next((a for a in anomalies if a.value == 100), None)
        assert spike_anomaly is not None
    
    def test_detect_anomalies_no_outliers(self):
        """Test anomaly detection with clean data."""
        values = [10 + np.random.normal(0, 0.1) for _ in range(30)]
        dates = [f"2024-01-{i:02d}" for i in range(30)]
        
        anomalies = TrendEngine.detect_anomalies(values, dates, z_threshold=3.0)
        
        # Should have few or no anomalies in clean data
        assert len(anomalies) <= 2
    
    def test_moving_average(self):
        """Test moving average calculation."""
        values = [float(i) for i in range(20)]
        ma = TrendEngine.moving_average(values, window=5)
        
        assert len(ma) == 20
        # First window-size-1 values should be NaN
        assert np.isnan(ma[0])
        assert np.isnan(ma[3])
        # After window, values should be smooth
        assert not np.isnan(ma[4])
        assert ma[4] == 2.0  # mean of [0,1,2,3,4]
    
    def test_pareto_analysis(self):
        """Test Pareto analysis on downtime categories."""
        categories = ["breakdown", "setup", "material", "operator"]
        values = [120, 80, 30, 10]
        
        result = TrendEngine.pareto_analysis(categories, values)
        
        assert len(result.categories) == 4
        assert result.categories[0] == "breakdown"  # highest first
        assert result.total == 240
        assert result.top_20_contributors[0] == "breakdown"
        assert result.top_20_pct > 0
    
    def test_full_analysis(self):
        """Test full trend analysis pipeline."""
        # Generate realistic data with upward OEE trend
        dates = [f"2024-01-{i:02d}" for i in range(1, 31)]
        oee = [80 + i * 0.3 + np.random.normal(0, 1) for i in range(30)]
        avail = [90 + i * 0.1 for i in range(30)]
        perf = [85 - i * 0.05 for i in range(30)]
        qual = [95 + i * 0.05 for i in range(30)]
        
        result = TrendEngine.full_analysis(
            oee_values=oee,
            avail_values=avail,
            perf_values=perf,
            qual_values=qual,
            dates=dates,
            downtime_categories=["breakdown", "setup"],
            downtime_values=[200, 150],
        )
        
        assert result.overall_direction in ("improving", "declining", "mixed")
        assert result.risk_level in ("low", "medium", "high")
        assert len(result.oee_ma_7) == 30
        assert len(result.oee_ma_30) == 30
        assert result.downtime_pareto is not None
    
    def test_full_analysis_to_dict(self):
        """Test serialization to dict."""
        dates = [f"2024-01-{i:02d}" for i in range(1, 15)]
        oee = [82 + i * 0.2 for i in range(14)]
        avail = [90 + i * 0.05 for i in range(14)]
        perf = [88 + i * 0.02 for i in range(14)]
        qual = [96 - i * 0.03 for i in range(14)]
        
        result = TrendEngine.full_analysis(oee, avail, perf, qual, dates)
        d = result.to_dict()
        
        assert "oee_trend" in d
        assert "anomalies" in d
        assert "overall_direction" in d
        assert "risk_level" in d


class TestTrendAnalysisNode:
    """Test the trend_analysis_node orchestrator."""
    
    def setup_method(self):
        """Create synthetic data."""
        self.csv_path = generate_synthetic_production(
            start_date="2024-01-01",
            end_date="2024-06-30",
            seed=42,
        )
    
    def test_trend_analysis_node_success(self):
        """Test trend analysis node with valid data."""
        from src.graph.state import GodinezState
        state = GodinezState()
        state.update({
            "query": "Show me the production trends",
            "intent": "trend",
            "csv_path": self.csv_path,
            "entities": {},
            "errors": [],
        })
        
        result = trend_analysis_node(state)
        
        assert "response" in result
        assert "machines_analyzed" in result["metadata"]
        assert len(result["metadata"]["machines_analyzed"]) > 0
        assert result["metadata"]["trend_analysis"] == "complete"
        assert "data_points" in result["metadata"]
        # Response should contain analysis output
        assert "OEE Trend:" in result["response"]
        assert "7-day forecast:" in result["response"]
    
    def test_trend_analysis_node_insufficient_data(self):
        """Test trend analysis with too few data points."""
        from src.graph.state import GodinezState
        
        # Generate a small dataset
        small_csv = generate_synthetic_production(
            start_date="2024-01-01",
            end_date="2024-01-01",
            seed=99,
        )
        
        state = GodinezState()
        state.update({
            "query": "Show trends",
            "intent": "trend",
            "csv_path": small_csv,
            "entities": {},
            "errors": [],
        })
        
        result = trend_analysis_node(state)
        
        assert "Insufficient data" in result["response"]
        assert result["metadata"]["trend_analysis"] == "insufficient_data"
    
    def test_trend_analysis_node_with_machine_filter(self):
        """Test trend analysis with machine filter."""
        from src.graph.state import GodinezState
        state = GodinezState()
        state.update({
            "query": "Show trends for Line-1",
            "intent": "trend",
            "csv_path": self.csv_path,
            "entities": {"machine": "Line-1"},
            "errors": [],
        })
        
        result = trend_analysis_node(state)
        
        assert result["metadata"]["trend_analysis"] == "complete"
        # Should only analyze the specified machine
        assert "Line-1" in result["metadata"]["machines_analyzed"]
    
    def test_trend_analysis_node_with_date_filter(self):
        """Test trend analysis with date range filter."""
        from src.graph.state import GodinezState
        state = GodinezState()
        state.update({
            "query": "Show Q1 trends",
            "intent": "trend",
            "csv_path": self.csv_path,
            "entities": {
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
            "errors": [],
        })
        
        result = trend_analysis_node(state)
        
        assert result["metadata"]["trend_analysis"] == "complete"
    
    def test_calc_per_period_oee(self):
        """Test per-period OEE calculation helper."""
        from src.tools.csv_reader import read_production_csv
        rows = read_production_csv(self.csv_path)
        
        # Filter to one machine and one date
        sample = [r for r in rows if r["machine_id"] == "Line-1"][:5]
        
        result = _calc_per_period_oee(sample)
        
        assert "oee" in result
        assert "availability" in result
        assert "performance" in result
        assert "quality" in result
        assert "dates" in result


class TestTrendInAnalyzeOrchestrator:
    """Test trend intent routing through analyze node."""
    
    def setup_method(self):
        """Setup synthetic data."""
        self.csv_path = generate_synthetic_production(
            start_date="2024-01-01",
            end_date="2024-06-30",
            seed=42,
        )
    
    def test_analyze_node_trend_intent(self):
        """Test analyze_node dispatches to trend handler."""
        from src.graph.state import GodinezState
        state = GodinezState()
        state.update({
            "query": "Show me the production trends over the last quarter",
            "intent": "trend",
            "csv_path": self.csv_path,
            "entities": {},
            "errors": [],
        })
        
        result = analyze_node(state)
        
        assert "response" in result
        assert "analysis_results" in result
        assert "trend" in result.get("analysis_results", {})
        assert result.get("metadata", {}).get("analyzed_intents") == ["trend"]
        assert result.get("metadata", {}).get("analysis_result_count") == 1


class TestChartGeneration:
    """Test trend chart generation via response_node."""
    
    def setup_method(self):
        """Setup synthetic data."""
        self.csv_path = generate_synthetic_production(
            start_date="2024-01-01",
            end_date="2024-06-30",
            seed=42,
        )
    
    def test_response_node_includes_trend_response(self):
        """Test response_node handles trend analysis output."""
        from src.graph.state import GodinezState
        
        # First run trend analysis
        state = GodinezState()
        state.update({
            "query": "Show me the production trends",
            "intent": "trend",
            "csv_path": self.csv_path,
            "entities": {},
            "errors": [],
        })
        
        trend_result = trend_analysis_node(state)
        state.update(trend_result)
        
        # Then run response node
        result = response_node(state)
        
        assert "response" in result
        # Response should contain the trend data
        assert "OEE Trend" in result["response"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
