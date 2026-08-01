"""
Tests for Godínez IndustrialEngineer workflow.

Phase 0: Basic smoke test to verify the workflow runs end-to-end.
Phase 1: OEE analysis — calculator, CSV reader, chart generation, end-to-end.
Phase 2: Intent classifier — multi-intent, low-confidence, entity extraction.
"""

import pytest
import sys
import os

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.graph import build_workflow


# ── Phase 0: Workflow smoke tests ──────────────────────────

def test_workflow_runs():
    """Test that the workflow executes end-to-end."""
    workflow, _ = build_workflow()
    app = workflow.compile()
    result = app.invoke({
        "query": "What's our OEE today?",
        "messages": [{"role": "user", "content": "What's our OEE today?"}],
    })
    assert "response" in result
    assert result["response"] is not None
    assert len(result["response"]) > 0


def test_empty_query_handling():
    """Test that empty queries are handled gracefully."""
    workflow, _ = build_workflow()
    app = workflow.compile()
    result = app.invoke({
        "query": "",
        "messages": [{"role": "user", "content": ""}],
    })
    assert "response" in result
    assert "error" in result["response"].lower() or "need" in result["response"].lower()


def test_intent_detection():
    """Test that intent is classified correctly."""
    workflow, _ = build_workflow()
    app = workflow.compile()
    result = app.invoke({
        "query": "What's our OEE today?",
        "messages": [{"role": "user", "content": "What's our OEE today?"}],
    })
    assert result.get("intent") is not None
    assert result["intent"] == "oee"


# ── Phase 1: OEE Calculator Tests ─────────────────────────

from src.tools.oee_calculator import calculate_oee, calculate_average_oee, OEEResult


class TestOEETCalculator:

    def test_oee_perfect_scenario(self):
        """Perfect conditions → OEE = 100%."""
        result = calculate_oee(
            planned_minutes=480, actual_run_minutes=480,
            downtime_minutes=0, ideal_cycle_time_seconds=30,
            total_count=960, good_count=960,
        )
        assert result.availability == 100.0
        assert result.performance == 100.0
        assert result.quality == 100.0
        assert result.oee == 100.0
        assert result.rating == "world_class"

    def test_oee_with_downtime(self):
        """480 planned, 420 run, 60 downtime."""
        result = calculate_oee(
            planned_minutes=480, actual_run_minutes=420,
            downtime_minutes=60, ideal_cycle_time_seconds=30,
            total_count=700, good_count=680,
        )
        assert result.availability == pytest.approx(87.5, abs=0.1)
        assert result.quality == pytest.approx(97.14, abs=0.1)
        assert 0 < result.oee < 100

    def test_oee_zero_values(self):
        """Zero inputs should not raise division by zero."""
        result = calculate_oee(0, 0, 0, 0, 0, 0)
        assert result.oee == 0.0
        assert result.availability == 0.0

    def test_oee_rating_classification(self):
        """Verify rating thresholds."""
        r1 = calculate_oee(480, 300, 180, 30, 600, 570)
        assert r1.rating == "critical"
        r2 = calculate_oee(480, 400, 80, 30, 800, 780)
        assert r2.rating == "needs_improvement"
        r3 = calculate_oee(480, 450, 30, 30, 850, 840)
        assert r3.rating == "good"
        r4 = calculate_oee(480, 470, 10, 30, 940, 935)
        assert r4.rating == "world_class"

    def test_oee_performance_capped_at_100(self):
        """Performance shouldn't exceed 100% even with unrealistically fast production."""
        result = calculate_oee(
            planned_minutes=480, actual_run_minutes=400,
            downtime_minutes=80, ideal_cycle_time_seconds=30,
            total_count=900, good_count=900,
        )
        assert result.performance <= 100.0


class TestAverageOEE:

    def test_average_oee_aggregation(self):
        """Average should aggregate totals, not average components."""
        r1 = calculate_oee(480, 420, 60, 30, 700, 680)
        r2 = calculate_oee(480, 450, 30, 30, 900, 890)
        avg = calculate_average_oee([r1, r2])
        assert avg.total_count == 1600
        assert avg.good_count == 1570
        assert avg.oee > 0


# ── Phase 1: CSV Reader Tests ─────────────────────────────

class TestCSVReader:

    def test_load_sample_csv(self):
        """Sample CSV should load without errors."""
        from src.tools.csv_reader import read_production_csv
        from pathlib import Path
        csv_path = Path(__file__).parent.parent / "data" / "sample_production.csv"
        assert csv_path.exists(), "Sample production CSV not found"
        data = read_production_csv(csv_path)
        assert len(data) > 0
        first = data[0]
        assert all(k in first for k in ["date", "machine_id", "total_count", "good_count"])
        assert isinstance(first["total_count"], int)
        assert isinstance(first["good_count"], int)

    def test_machine_ids_extraction(self):
        """Should extract unique machine IDs."""
        from src.tools.csv_reader import read_production_csv, get_machine_ids
        from pathlib import Path
        csv_path = Path(__file__).parent.parent / "data" / "sample_production.csv"
        data = read_production_csv(csv_path)
        machines = get_machine_ids(data)
        assert isinstance(machines, list)
        assert len(machines) > 0

    def test_date_range_extraction(self):
        """Should extract date range from data."""
        from src.tools.csv_reader import read_production_csv, get_date_range
        from pathlib import Path
        csv_path = Path(__file__).parent.parent / "data" / "sample_production.csv"
        data = read_production_csv(csv_path)
        start, end = get_date_range(data)
        assert start <= end


# ── Phase 1: OEE Node Tests ───────────────────────────────

class TestOEENode:

    def test_oee_node_runs(self):
        """OEE node should process data and return a response."""
        from src.graph.nodes.oee_analysis import oee_analysis_node
        result = oee_analysis_node({
            "query": "What's our OEE?",
            "intent": "oee",
            "messages": [{"role": "user", "content": "What's our OEE?"}],
        })
        assert "response" in result
        assert len(result["response"]) > 0

    def test_oee_node_contains_metrics(self):
        """Response should include OEE metrics and percentages."""
        from src.graph.nodes.oee_analysis import oee_analysis_node
        result = oee_analysis_node({"query": "What's our OEE?", "intent": "oee"})
        assert "OEE" in result["response"]
        assert "%" in result["response"]


# ── Phase 1: End-to-End ──────────────────────────────────

class TestEndToEnd:

    def test_e2e_oee_query(self):
        """Full workflow: query → intent → OEE analysis → response."""
        workflow, _ = build_workflow()
        app = workflow.compile()
        result = app.invoke({
            "query": "What's our OEE today?",
            "messages": [{"role": "user", "content": "What's our OEE today?"}],
        })
        assert "response" in result
        assert result["intent"] == "oee"
        assert "OEE" in result["response"]
        assert "%" in result["response"]


# ── Phase 2: Classifier Tests ─────────────────────────────

from src.graph.nodes.classify import classify_node, _keyword_fallback


class TestClassifyNode:

    def test_classify_oee_intent(self):
        """OEE query should return oee intent via keyword fallback."""
        result = classify_node({
            "query": "What's our OEE today?",
            "messages": [{"role": "user", "content": "What's our OEE today?"}],
        })
        assert result["intent"] == "oee"
        assert result["confidence"] == 0.7  # keyword fallback confidence

    def test_classify_multi_intent(self):
        """Multi-intent query (OEE + bottleneck) should pick best match."""
        result = classify_node({
            "query": "Show me OEE and find bottlenecks on Line 3",
            "messages": [{"role": "user", "content": "Show me OEE and find bottlenecks"}],
        })
        # Keyword fallback picks first match; both oee and bottleneck keywords present
        assert result["intent"] in ("oee", "bottleneck", "general")

    def test_classify_safety_intent(self):
        """Safety-related query should classify as safety."""
        result = classify_node({
            "query": "Safety incident yesterday on Machine 5",
            "messages": [{"role": "user", "content": "Safety incident yesterday"}],
        })
        assert result["intent"] == "safety"
        assert result["confidence"] >= 0.4

    def test_classify_cost_intent(self):
        """Cost/waste query should classify as cost."""
        result = classify_node({
            "query": "What's our scrap cost this week?",
            "messages": [{"role": "user", "content": "scrap cost this week"}],
        })
        assert result["intent"] == "cost"

    def test_classify_general_intent(self):
        """Unrecognized query should fall back to general."""
        result = classify_node({
            "query": "Tell me about the team lunch",
            "messages": [{"role": "user", "content": "team lunch"}],
        })
        assert result["intent"] == "general"
        assert result["confidence"] < 0.5

    def test_classify_human_review_flag(self):
        """Low-confidence queries should set human_review=True."""
        result = classify_node({
            "query": "Tell me about the team lunch",
        })
        assert result["human_review"] is True

        high_conf = classify_node({
            "query": "What's our OEE today?",
        })
        assert high_conf["human_review"] is False

    def test_classify_metadata_contains_method(self):
        """Metadata should include classify_method (primary/ollama/keyword_fallback)."""
        result = classify_node({
            "query": "What's our OEE today?",
        })
        assert "classify_method" in result["metadata"]
        assert result["metadata"]["classify_method"] in (
            "primary", "ollama", "keyword_fallback"
        )


class TestKeywordFallback:

    def test_keyword_oee(self):
        r = _keyword_fallback("What is our OEE today?")
        assert r.intent == "oee"
        assert r.confidence == 0.7

    def test_keyword_bottleneck(self):
        r = _keyword_fallback("Find the bottleneck on Line 3")
        assert r.intent == "bottleneck"
        assert r.confidence == 0.7

    def test_keyword_safety(self):
        r = _keyword_fallback("OSHA compliance check")
        assert r.intent == "safety"
        assert r.confidence == 0.7

    def test_keyword_cost(self):
        r = _keyword_fallback("What is the scrap rate and rework cost?")
        assert r.intent == "cost"
        assert r.confidence == 0.7

    def test_keyword_unknown(self):
        r = _keyword_fallback("Hey, how's the weather?")
        assert r.intent == "general"
        assert r.confidence == 0.4


class TestOrchestratorNode:
    """Phase 2 Step 2: Orchestrator Analysis Node tests."""

    def test_analyze_oee_dispatch(self):
        """OEE intent should dispatch to oee_analysis_node."""
        from src.graph.nodes.analyze import analyze_node
        result = analyze_node({
            "query": "What's our OEE?",
            "intent": "oee",
            "messages": [{"role": "user", "content": "What's our OEE?"}],
        })
        assert "response" in result
        assert "OEE" in result["response"]
        assert "%" in result["response"]

    def test_analyze_unimplemented_intent(self):
        """Unimplemented intent should return 'not yet implemented' message."""
        from src.graph.nodes.analyze import analyze_node
        result = analyze_node({
            "query": "Show me safety violations",
            "intent": "safety",
            "messages": [{"role": "user", "content": "Show me safety violations"}],
        })
        assert "not yet implemented" in result["response"].lower()
        assert "oee" in result["response"]  # Should list implemented intents

    def test_analyze_accumulates_results(self):
        """Results should be accumulated in analysis_results dict."""
        from src.graph.nodes.analyze import analyze_node
        result = analyze_node({
            "query": "OEE analysis",
            "intent": "oee",
            "messages": [{"role": "user", "content": "OEE analysis"}],
        })
        assert "analysis_results" in result
        assert result["analysis_results"] is not None
        assert isinstance(result["analysis_results"], dict)

    def test_analyze_metadata_tracking(self):
        """Metadata should track which intents were analyzed."""
        from src.graph.nodes.analyze import analyze_node
        result = analyze_node({
            "query": "OEE analysis",
            "intent": "oee",
            "messages": [{"role": "user", "content": "OEE analysis"}],
        })
        assert "analyzed_intents" in result["metadata"]
        assert "oee" in result["metadata"]["analyzed_intents"]
        assert result["metadata"]["analysis_result_count"] >= 1

    def test_analyze_bottleneck_dispatch(self):
        """Bottleneck intent should dispatch to bottleneck_node."""
        from src.graph.nodes.analyze import analyze_node
        result = analyze_node({
            "query": "Find bottlenecks on Line 3",
            "intent": "bottleneck",
            "messages": [{"role": "user", "content": "Find bottlenecks"}],
        })
        assert "response" in result
        assert "Bottleneck" in result["response"]
        assert "Findings" in result["response"]

    def test_analyze_cost_dispatch(self):
        """Cost intent should dispatch to cost_node."""
        from src.graph.nodes.analyze import analyze_node
        result = analyze_node({
            "query": "What are our scrap costs?",
            "intent": "cost",
            "messages": [{"role": "user", "content": "scrap costs"}],
        })
        assert "response" in result
        assert "Cost" in result["response"]
        assert "$" in result["response"]


class TestBottleneckNode:
    """Phase 2 Step 3: Bottleneck detection node tests."""

    def test_bottleneck_node_runs(self):
        """Bottleneck node should process data and return findings."""
        from src.graph.nodes.bottleneck import bottleneck_node
        result = bottleneck_node({
            "query": "Find bottlenecks",
            "intent": "bottleneck",
            "messages": [{"role": "user", "content": "Find bottlenecks"}],
        })
        assert "response" in result
        assert "Bottleneck" in result["response"]

    def test_bottleneck_returns_metadata(self):
        """Bottleneck node should return metadata with findings count."""
        from src.graph.nodes.bottleneck import bottleneck_node
        result = bottleneck_node({
            "query": "Find bottlenecks",
            "intent": "bottleneck",
        })
        assert "metadata" in result
        assert "total_findings" in result["metadata"]
        assert result["metadata"]["total_findings"] >= 0

    def test_bottleneck_has_findings(self):
        """Bottleneck analysis should detect at least some findings."""
        from src.graph.nodes.bottleneck import bottleneck_node
        result = bottleneck_node({
            "query": "Find bottlenecks",
            "intent": "bottleneck",
        })
        # Should have at least some throughput findings
        bottleneck_data = result["analysis_results"].get("bottleneck", {})
        assert bottleneck_data.get("findings_count", 0) > 0


class TestCostNode:
    """Phase 2 Step 3: Cost analysis node tests."""

    def test_cost_node_runs(self):
        """Cost node should process data and return cost breakdown."""
        from src.graph.nodes.cost_analysis import cost_node
        result = cost_node({
            "query": "What are our scrap costs?",
            "intent": "cost",
            "messages": [{"role": "user", "content": "scrap costs"}],
        })
        assert "response" in result
        assert "Cost" in result["response"]
        assert "$" in result["response"]

    def test_cost_returns_metadata(self):
        """Cost node should return metadata with waste cost."""
        from src.graph.nodes.cost_analysis import cost_node
        result = cost_node({
            "query": "What are our scrap costs?",
            "intent": "cost",
        })
        assert "metadata" in result
        assert "total_waste_cost" in result["metadata"]
        assert result["metadata"]["total_waste_cost"] >= 0

    def test_cost_has_breakdown(self):
        """Cost analysis should include scrap, rework, and downtime costs."""
        from src.graph.nodes.cost_analysis import cost_node
        result = cost_node({
            "query": "What are our scrap costs?",
            "intent": "cost",
        })
        cost_data = result["analysis_results"]["cost"]
        assert "scrap_cost" in cost_data
        assert "rework_cost" in cost_data
        assert "downtime_cost" in cost_data
        assert "total_waste_cost" in cost_data


class TestMultiIntentChaining:
    """Phase 2 Step 3: Multi-intent chaining tests."""

    def test_analyze_multiple_handlers_registered(self):
        """All five handlers should be registered in orchestrator."""
        from src.graph.nodes.analyze import ANALYSIS_HANDLERS
        assert "oee" in ANALYSIS_HANDLERS
        assert "bottleneck" in ANALYSIS_HANDLERS
        assert "cost" in ANALYSIS_HANDLERS
        assert "trend" in ANALYSIS_HANDLERS
        assert "load_dataset" in ANALYSIS_HANDLERS
        assert len(ANALYSIS_HANDLERS) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
