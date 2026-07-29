# Godínez IndustrialEngineer — Implementation Plan

> Version 0.8 | Created 2026-07-27 | Last Updated 2026-07-29 | Status: Phase 3 Complete (Trend Analysis ✅) | Next: Phase 4 Bottleneck & Cost

---

## Overview

Phase-based rollout from proof-of-concept to production-ready agent. Each phase builds on the previous and delivers a working artifact.

**Total phases:** 6  
**Reference architecture:** NVIDIA AI-Q Blueprint (`NVIDIA-AI-Blueprints/aiq-research-assistant`)  
**LangGraph pattern:** Supervisor / multi-agent orchestration

---

## Phase 0: Skeleton & Tooling (Week 1) ✅ COMPLETE

**Goal:** Repo structure, basic graph, working CLI — "Hello World" of the agent.  
**Status:** Complete ✅ — 2026-07-27  
**Commit:** `29677fc`

### Completed
- [x] Create repo with standard structure (Python 3.13, .venv)
- [x] `pyproject.toml` + `requirements.txt` with dependencies
- [x] `state.py` — Pydantic GodinezState (query, intent, response, metadata)
- [x] `workflow.py` — minimal StateGraph: intake → router → analyze → response → END
- [x] `main.py` — CLI entry point accepting text input
- [x] Keyword-based router (Phase 0 style, not LLM)
- [x] .gitignore, README.md
- [x] Test suite (3 smoke tests → expanded later)

### Notes
- Phase 0 was purely rule-based — no LLM calls
- Graph pipeline runs end-to-end successfully
- Pushed to GitHub

### Reference
- `langchain-ai/langgraph-example` — basic StateGraph pattern

---

## Phase 1: OEE Analysis Engine (Week 2) ✅ COMPLETE

**Goal:** First real capability — calculate, analyze, and display OEE.

### Completed
- [x] `tools/oee_calculator.py` — deterministic OEE math with OEEResult dataclass
  - OEE = Availability × Performance × Quality
  - Rating classification: critical (<75%), needs_improvement (75-85%), good (85-90%), world_class (90%+)
  - Recommendation engine: picks lowest component (availability/performance/quality) and returns tailored advice
  - `calculate_average_oee()` — weighted aggregation across multiple shifts
- [x] `tools/csv_reader.py` — read and validate production log CSVs
  - Required columns: date, shift, machine_id, planned/actual/run minutes, ideal cycle time, counts, downtime reason
  - Helper functions: `get_machine_ids()`, `get_date_range()`, `filter_by_date()`, `filter_by_machine()`
- [x] `tools/chart_generator.py` — matplotlib charts (non-interactive Agg backend)
  - OEE trend chart: dual-panel (components line chart + OEE bar chart with rating labels)
  - Downtime pie chart: breakdown by reason with total summary
- [x] `data/sample_production.csv` — synthetic test data (multiple shifts, machines, reasons)
- [x] `graph/nodes/oee_analysis.py` — full OEE analysis node
  - Reads CSV → calculates per-shift OEE → aggregates → generates charts → builds response
  - Structured metadata: oee_score, oee_rating, data_points, date_range
- [x] `graph/nodes/intake.py` — query validation + timestamp
- [x] `graph/nodes/router.py` — keyword-based intent routing (Phase 0 style)
- [x] `graph/nodes/response.py` — formatted response with intent header
- [x] CLI tested: `python main.py "What's our OEE today?"` → full OEE report
- [x] **15/15 pytest tests passing** (5.8s)

### Test Coverage
| Test | Status |
|------|--------|
| `test_workflow_runs` | ✅ |
| `test_empty_query_handling` | ✅ |
| `test_intent_detection` | ✅ |
| `test_oee_perfect_scenario` | ✅ |
| `test_oee_with_downtime` | ✅ |
| `test_oee_zero_values` | ✅ |
| `test_oee_rating_classification` | ✅ |
| `test_oee_performance_capped_at_100` | ✅ |
| `test_average_oee_aggregation` | ✅ |
| `test_load_sample_csv` | ✅ |
| `test_machine_ids_extraction` | ✅ |
| `test_date_range_extraction` | ✅ |
| `test_oee_node_runs` | ✅ |
| `test_oee_node_contains_metrics` | ✅ |
| `test_e2e_oee_query` | ✅ |

### Example Output
```
OEE Analysis Report
==================================================
Date Range: 2024-01-01 to 2024-01-14
Total Shifts Analyzed: 84

Overall OEE Score: 86.1%
Rating: Good

Components:
  • Availability: 86.1%
  • Performance:  100.0%
  • Quality:      99.1%

Total Production:
  • Total Units:  72,000
  • Good Units:   71,380
  • Defects:      620 (0.9%)

Recommendation: Focus on reducing downtime...
Top Downtime Causes:
  • breakdown: 450 minutes
  • setup: 315 minutes
  • material_shortage: 265 minutes
```

### Notes
- Recommendation text is **deterministic/hardcoded** — picks lowest OEE component and returns tailored advice from a dict lookup
- No LLM connection yet — pure math, verifiable, no hallucination risk
- Charts saved to `/tmp/` (temporary, suitable for demo)

### Reference
- `SayamAlt/Financial-Research-Advisory-Agent` — data ingestion → calculation → output pattern

---

## Phase 2: Router Upgrade & Multi-Intent Support (Week 3) ✅ COMPLETE

**Goal:** Agent can handle multiple query types via LLM-based intent classification and orchestration.

### Completed
- [x] **Step 1: LLM-Based Intent Classification** ✅ — 2026-07-29
  - Add LangChain LLM integration for intent classification
  - Return confidence score + detected entities (machine IDs, date ranges)
  - Low-confidence → fallback to keyword matching + human_review flag
  - New node: `classify` between `intake` and `router`
  - New tests: multi-intent queries, low-confidence handling, entity extraction
  - 3-tier fallback chain: DGX vLLM → local ollama → keyword matching
  - **12 new tests** (total 27 at this point)

- [x] **Step 2: Orchestrator Analysis Node** ✅ — 2026-07-29
  - `analyze` node becomes dispatcher calling intent-specific analysis nodes
  - Each analysis (OEE, bottleneck, cost, etc.) runs as its own tool/node
  - Support multi-tool chaining (e.g., OEE + bottleneck in one query)
  - Extracts handler metadata and accumulates in `state.analysis_results`
  - Metadata tracking: `analyzed_intents`, `analysis_result_count`
  - **4 new tests** (total 31, all passing in 8.71s)

- [x] **Step 3: New Analysis Nodes** ✅ — 2026-07-29
  - `src/graph/nodes/bottleneck.py` — throughput/constraint detection (cycle time variance, downtime, capacity, throughput)
  - `src/graph/nodes/cost_analysis.py` — scrap/rework/waste cost estimation
  - Both registered in `analyze.py` ANALYSIS_HANDLERS
  - **9 new tests** (total 40 at this point)

- [x] **Observability** ✅ — 2026-07-29
  - LangSmith tracing module (`src/observability/tracing.py`)
  - Structured JSON logging with correlation IDs (`src/observability/logger.py`)
  - Execution metrics tracker (`src/observability/metrics.py`)
  - Metadata: `latency_ms`, `tokens_used`, `node_execution_order`, `session_id`
  - Integrated into workflow (all nodes wrapped with metrics tracking)
  - CLI supports `--session` and `--trace` flags
  - **20 new tests** (total 60 at this point)

- [x] **REST API Endpoint** ✅ — 2026-07-29
  - FastAPI: `POST /api/query` accepting `{"query": "...", "user_id": "..."}`
  - Returns JSON with response, intent, metadata, chart paths
  - Same workflow as CLI — different entry point
  - `src/api/app.py` + `tests/test_api.py` (9 tests, all passing)
  - CORS middleware enabled for browser/frontend access

### Deliverables
- LLM-based intent classifier with confidence scoring ✅
- Orchestrator routing to multiple analysis types ✅
- New analysis nodes: bottleneck + cost ✅
- REST API endpoint
- ~25 tests covering router, API, and multi-intent flows ✅ (now 69: 60 core + 9 API)
- LangSmith observability ✅

### What's Out of Scope
- LLM-based chat (Phase 3)
- Human-in-the-loop approval (Phase 3)
- Database persistence (Phase 3)
- Multi-machine factory context (Phase 4)

### Reference
- `aws-samples/langgraph-multi-agent` — orchestrator/routing pattern
- `langchain-ai/deepagents` — planning tool pattern

---

## Phase 3: Trend Analysis & Visualization (Week 4) ✅ COMPLETE

**Goal:** Statistical analysis and chart generation for production data.
**Status:** Complete ✅ — 2026-07-29

### Completed ✅
- [x] **Trend Engine** (`tools/analysis/trend_engine.py`):
  - ✅ Linear regression trend detection (up/down/stable) with R² scoring
  - ✅ Anomaly detection (z-score method with zero-std edge case handling)
  - ✅ Moving averages (7-day, 30-day)
  - ✅ Pareto analysis (80/20 rule with top contributors)
  - ✅ Forecasting (7-day and 30-day linear projections)
  - ✅ **Extended forecasts**: 60/90 day linear projections
  - ✅ **Timeseries decomposition**: Extract trend/seasonality/noise components
  - ✅ `to_dict()` serialization for all result types
  - ✅ **Full analysis workflow**: `full_analysis()` integrates all modules

- [x] **Trend Analysis Node** (`graph/nodes/trend_analysis.py`):
  - ✅ Multi-machine query support with per-line OEE calculation
  - ✅ Date range and machine filtering
  - ✅ Orchestrator integration (dispatched via `intent == "trend"`)
  - ✅ Structured metadata: `trend_analysis`, `machines_analyzed`, `data_points`
  - ✅ **6-month integration test** with synthetic data

- [x] **Chart Templates** (`tools/chart_templates.py`):
  - ✅ OEE trend chart with component breakdown and forecast overlay
  - ✅ Pareto chart with 80/20 threshold annotation
  - ✅ Control chart (X-bar) with UCL/LCL and outlier highlighting
  - ✅ Forecast chart with confidence interval
  - ✅ Multi-series trend line chart

- [x] **Chart Palette** (`tools/chart_palette.py`):
  - ✅ Centralized color scheme (OEE components, thresholds, control limits)
  - ✅ Consistent matplotlib styling via `apply_style()`
  - ✅ Utility functions: `format_percent()`, `format_number()`, `save_chart()`

- [x] **Response Node Integration** (`graph/nodes/response.py`):
  - ✅ Auto-generates charts for trend queries
  - ✅ **Base64 chart embedding** in API responses
  - ✅ Returns chart paths as attachments
  - ✅ Metadata tracking: `chart_count`

- [x] **Test Suite** — **21/21 tests passing** for trend engine + integration
  - ✅ Trend engine: linear regression, anomaly detection, moving averages, Pareto
  - ✅ Trend node: full analysis, date filtering, machine filtering, insufficient data
  - ✅ Orchestrator: trend intent dispatch, response formatting

### Deliverables
- ✅ Automated trend detection with risk scoring (critical/needs_improvement/good/world_class)
- ✅ Anomaly detection with severity classification (mild/moderate/severe)
- ✅ Pareto analysis for downtime/waste ranking
- ✅ OEE component trend tracking (availability, performance, quality)
- ✅ 7/30/60/90 day forecasts
- ✅ Timeseries decomposition (trend/seasonality/noise)
- ✅ OEE trend charts with forecast overlay
- ✅ Control charts with outlier detection
- ✅ Pareto charts with 80/20 annotations
- ✅ Base64 chart embedding in API responses
- ✅ 6-month integration test with synthetic data

### Deliverables Status
- ✅ Automated trend detection with risk scoring (critical/needs_improvement/good/world_class)
- ✅ Anomaly detection with severity classification (mild/moderate/severe)
- ✅ Pareto analysis for downtime/waste ranking
- ✅ OEE component trend tracking (availability, performance, quality)
- ✅ 7/30 day forecasts
- ✅ OEE trend charts with forecast overlay
- ✅ Control charts with outlier detection
- ✅ Pareto charts with 80/20 annotations
- ⏳ 60/90 day forecasts (pending)
- ⏳ Timeseries decomposition (pending)

### Architecture
```
Intent: "trend"
  → trend_analysis_node()
    → _calc_per_period_oee() [per-date aggregation]
    → TrendEngine.full_analysis()
      ├── analyze_trend() ×4 (OEE, avail, perf, quality)
      ├── moving_average() ×2 (7-day, 30-day)
      ├── detect_anomalies()
      └── pareto_analysis()
    → Response: text summary + generated charts
```

### Reference
- `statsmodels` library for timeseries decomposition (future)
- `pandas` rolling window operations
- Manufacturing SPC (Statistical Process Control) methods
- NVIDIA AI-Q Blueprint (forecasting patterns)

---

## Phase 4: Bottleneck Detection & Cost Analysis (Week 5)

**Goal:** Two more analysis nodes — identifying constraints and quantifying waste.

### Tasks
- [ ] Extend state with `BottleneckResult` and `CostResult` models
- [ ] Implement `tools/analysis/bottleneck_detector.py`:
  - Line balance calculation
  - Cycle time variance analysis
  - Constraint identification (highest WIP, longest queue)
  - Improvement suggestions (Theory of Constraints)
- [ ] Implement `tools/analysis/cost_estimator.py`:
  - Scrap cost calculation
  - Rework cost tracking
  - ROI model for improvement suggestions
  - Waste Pareto ranking
- [ ] Add `bottleneck_detect` and `cost_analysis` nodes to graph
- [ ] Update router for new intent categories
- [ ] Test with synthetic line data

### Deliverables
- Bottleneck identification with severity ratings
- Cost analysis with waste breakdown
- ROI projections for improvement suggestions

### Reference
- Theory of Constraints (Goldratt)
- Lean Six Sigma cost-of-quality framework
- `mayankysharma/langgraph-code-agent` — QA pipeline pattern

---

## Phase 5: Safety Audit & Human-in-the-Loop (Week 6)

**Goal:** Regulatory compliance analysis with human review gate.

### Tasks
- [ ] Extend state with `SafetyResult` model
- [ ] Implement `knowledge/osha_standards.md` — RAG document set
- [ ] Implement `tools/knowledge/osha_rag.py`:
  - Embed OSHA standards (using local embedding model)
  - Similarity search against incident descriptions
  - Compliance gap detection
- [ ] Implement `graph/nodes/safety_audit.py`:
  - Parse incident reports
  - Match against OSHA categories
  - Generate compliance score
- [ ] Implement `graph/nodes/human_review.py`:
  - Graph pauses at human_review for safety-critical findings
  - CLI prompts user for approval/rejection/additional context
- [ ] Add conditional edge: safety findings → human_review → synthesis
- [ ] Implement `graph/nodes/time_study.py` — basic time study analysis

### Deliverables
- Safety compliance scoring
- Incident-to-regulation matching
- Human-in-the-loop gate for safety findings
- Time study calculator

### Reference
- NVIDIA AI-Q checkpointing pattern (for pause/resume)
- Safety regulations: 29 CFR 1910 (general industry), 29 CFR 1926 (construction)

---

## Phase 6: Production Hardening (Week 7-8)

**Goal:** Polish, document, deploy as API service.

### Tasks
- [ ] Implement `main.py` CLI with subcommands:
  - `godinez analyze "query"` — run agent
  - `godinez report` — generate report from last analysis
  - `godinez config` — view/edit thresholds
  - `godinez data` — import data files
- [ ] Implement FastAPI server (`src/api/`):
  - `POST /api/query` — run agent with query
  - `POST /api/data` — upload data files
  - `GET /api/results/{session_id}` — retrieve past analyses
- [ ] Set up PostgreSQL persistence (configurable)
- [ ] Add comprehensive tests:
  - Unit tests for calculators (OEE, cost, bottleneck)
  - Integration tests for graph nodes
  - E2E tests for CLI
- [ ] Add NeMo Agent Toolkit profiling (optional)
- [ ] Write comprehensive README:
  - Setup guide
  - Usage examples
  - Configuration reference
  - Architecture diagram
- [ ] Add sample production data for demo
- [ ] Code review + cleanup

### Deliverables
- Production-ready agent with CLI + API
- Comprehensive tests
- Full documentation
- Demo data set

---

## Current File Structure

```
godinez-industrial-engineer/
├── src/
│   ├── graph/
│   │   ├── workflow.py          # Main StateGraph: intake → classify → router → analyze → response → END
│   │   ├── state.py             # Pydantic GodinezState (extends MessagesState)
│   │   ├── nodes/
│   │   │   ├── intake.py        # Query validation + timestamp
│   │   │   ├── classify.py      # LLM-based intent classification (Phase 2)
│   │   │   ├── router.py        # Keyword-based intent routing (Phase 0)
│   │   │   ├── analyze.py       # Orchestrator → dispatches to intent-specific nodes
│   │   │   ├── response.py      # Formatted response builder
│   │   │   └── oee_analysis.py  # Phase 1: full OEE analysis
│   │   └── __init__.py
│   ├── tools/
│   │   ├── oee_calculator.py    # Deterministic OEE math + classification
│   │   ├── csv_reader.py        # CSV parsing + filters
│   │   └── chart_generator.py   # matplotlib charts (Agg backend)
│   └── config.py
├── data/
│   └── sample_production.csv    # Demo data (84 shifts, multiple machines)
│   ├── observability/
│   │   ├── __init__.py      # Observability module entry point
│   │   ├── logger.py        # Structured JSON logging with correlation IDs
│   │   ├── tracing.py       # LangSmith integration for workflow tracing
│   │   └── metrics.py       # Execution metrics tracking
│   └── config.py
├── data/
│   └── sample_production.csv    # Demo data (84 shifts, multiple machines)
├── tests/
│   ├── conftest.py              # LLM mocks for workflow tests
│   ├── test_workflow.py         # 40 tests (all passing)
│   ├── test_observability.py    # 20 tests (all passing)
│   └── test_api.py              # 9 tests (all passing)
├── src/
│   └── api/
│       └── app.py               # FastAPI REST API (Phase 2)
├── main.py                      # CLI entry point
├── pyproject.toml               # Project config + dev deps
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Factory data inaccessible (no API/SQL) | High | High | Start with CSV imports, add connectors later |
| LLM hallucination in analysis | Medium | High | Keep calculators deterministic (pandas/math), use LLM only for routing/synthesis |
| Scope creep (too many analysis types) | Medium | Medium | Stick to Phase 1-3 before expanding |
| Performance with large datasets | Low | Medium | Chunk processing, cache results |
| Safety regulation accuracy | Medium | Critical | Always flag as "informational, not legal advice"; human review mandatory |

---

## Success Criteria

- [x] Agent processes natural language queries about manufacturing data
- [x] OEE calculation is accurate and verifiable (deterministic, no LLM dependency)
- [x] Trends are detected and forecasted with confidence intervals
- [x] Bottlenecks are identified with clear reasoning
- [x] Reports are generated in professional format with embedded charts
- [ ] Safety findings require human approval
- [x] Code is testable and documented (90/90 tests passing)
- [x] Runs on DGX locally (no external API dependency for core analysis)

---

## Architecture Decision Log

### 2026-07-28: Recommendation Engine is Deterministic (Hardcoded)
**Decision:** OEE recommendations are hardcoded dict lookups based on lowest component, NOT LLM-generated.
**Reasoning:** Phase 1 prioritizes verifiability and zero hallucination risk. OEE is deterministic math; recommendations should match that level of trustworthiness. LLM-based recommendations come in Phase 2.
**Trade-off:** Less nuanced than LLM advice, but fully auditable and consistent.

### 2026-07-28: Router Uses Keyword Matching (Phase 0)
**Decision:** Intent routing is keyword-based, not LLM-based, at Phase 1.
**Reasoning:** Simple, fast, deterministic. LLM classification is planned for Phase 2.
**Trade-off:** Limited intent vocabulary, no confidence scoring, no entity extraction.

### 2026-07-29: 3-Tier LLM Fallback Chain
**Decision:** Intent classifier uses a strict fallback chain: DGX vLLM → local ollama → keyword matching.
**Reasoning:** Reliability — if DGX is slow/unreachable, fall back gracefully. Local ollama provides immediate fallback. Keyword matching is the last resort.
**Trade-off:** Slightly more complex setup, but ensures agent always responds.

### 2026-07-29: Orchestrator Analysis Node Design
**Decision:** `analyze.py` orchestrator extracts metadata from handler results and accumulates in `state.analysis_results`.
**Reasoning:** Enables multi-tool chaining — multiple analysis nodes can contribute results that get merged. Each handler returns its own structured result.
**Trade-off:** Slightly more complex than direct return, but future-proofs for multi-intent queries.
