# Godínez IndustrialEngineer — Implementation Plan

> Version 1.4.0 | Created 2026-07-27 | Last Updated 2026-07-31 | Status: Phase 6 Complete ✅ | Phase 5 (Safety Audit): Not Started ⏳

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
  - `src/api/app.py` + `tests/test_api.py` (12 tests, all passing)
  - CORS middleware enabled for browser/frontend access

### Deliverables
- LLM-based intent classifier with confidence scoring ✅
- Orchestrator routing to multiple analysis types ✅
- New analysis nodes: bottleneck + cost ✅
- REST API endpoint
- ~25 tests covering router, API, and multi-intent flows ✅ (now 81: 60 core + 21 API/trend/observability)
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

## Phase 4: Bottleneck Detection & Cost Analysis (Week 5) ✅ COMPLETE

**Goal:** Two more analysis nodes — identifying constraints and quantifying waste.
**Status:** Complete ✅ — 2026-07-30
**Total tests:** 115 passing (11.09s)

### Completed ✅
- [x] **Step 4.0: State Models & Synthetic Data** ✅
  - `BottleneckResult` model — `state.py` (constraint_station, findings, metrics, severity)
  - `CostResult` model — `state.py` (breakdown, roi_projections, waste_pareto)
  - `CostBreakdown` + `BottleneckFinding` Pydantic models
  - `tools/synthetic_data.py` — 3 generators (production, bottleneck, cost)
  - Synthetic data supports realistic constraint/cost scenarios (Line-2 bottleneck pattern)

- [x] **Step 4.1: Bottleneck Detector Engine** ✅
  - `tools/analysis/bottleneck_detector.py` — `BottleneckDetector.analyze(rows)`
  - Line balance calculation (balance_delay_pct, theoretical_best_station_time)
  - Cycle time variance analysis (per-station std dev, coefficient of variation)
  - Constraint identification (highest avg cycle time, throughput ranking)
  - Improvement suggestions (Theory of Constraints prioritization)
  - Severity scoring: critical (>30% delay), high (20-30%), medium (10-20%), low (<10%)
  - `to_dict()` serialization

- [x] **Step 4.2: Cost Estimator Engine** ✅
  - `tools/analysis/cost_estimator.py` — `CostEstimator.analyze(rows, config)`
  - Scrap cost calculation (units × scrap rate × cost_per_part)
  - Rework cost tracking (estimated rework minutes × labor_rate)
  - Downtime cost (total_downtime_min × downtime_cost_per_min)
  - ROI model for improvement suggestions
  - Waste Pareto ranking (ParetoResult with top contributors)
  - Configurable thresholds: scrap_rate_warn=5%, cost_per_part, labor_rate, downtime_cost_per_min
  - `to_dict()` serialization with breakdown + roi_projections + waste_pareto

- [x] **Step 4.3: Graph Integration + API** ✅
  - `graph/nodes/bottleneck.py` — `bottleneck_node()`: reads CSV, runs `BottleneckDetector`, returns structured result
  - `graph/nodes/cost_analysis.py` — `cost_analysis_node()`: reads CSV + config thresholds, runs `CostEstimator`
  - `analyze.py` orchestrator: `ANALYSIS_HANDLERS` dict with oee/bottleneck/cost/trend handlers
  - `router.py`: INTENT_KEYWORDS extended with bottleneck/cost terms
  - `classify.py`: VALID_INTENTS extended, `_keyword_fallback` handles bottleneck/cost queries
  - `POST /api/query` supports all intents (no filtering — same workflow for all)
  - Response includes structured metadata: findings_count, total_waste_cost, analysis_result_count

- [x] **Step 4.4: Integration Tests** ✅
  - `tests/test_phase4.py` — 25 tests:
    - State model tests (BottleneckResult, CostResult, nested models)
    - Bottleneck detector tests (line balance, severity, constraint identification)
    - Cost estimator tests (scrap cost, ROI projections, serialization)
    - Synthetic data generation tests (production, bottleneck, cost CSVs)
    - Full pipeline integration (generate → analyze → verify)
  - Workflow tests (bottleneck_node, cost_node, multi-intent chaining)
  - All 115 tests passing

### Deliverables
- ✅ Bottleneck identification with severity ratings (critical/high/medium/low)
- ✅ Cost analysis with waste breakdown (scrap, rework, downtime)
- ✅ ROI projections for improvement suggestions
- ✅ Line balance analysis with constraint identification
- ✅ Waste Pareto ranking
- ✅ Synthetic data generators for testing
- ✅ Full integration with workflow (classify → router → analyze → response)

### Architecture
```
Intent: "bottleneck" / "cost"
  → classify_node() [LLM → keyword → fallback]
  → router_node() [keyword dispatch]
  → analyze_node() [ANALYSIS_HANDLERS dispatch]
    → bottleneck_node() [BottleneckDetector.analyze(rows)]
      → _detect_throughput_constraints()
      → _analyze_cycle_time_variance()
      → _calculate_line_balance()
    → cost_analysis_node() [CostEstimator.analyze(rows, config)]
      → _calc_scrap_cost()
      → _calc_rework_cost()
      → _calc_downtime_cost()
      → _estimate_roi()
  → response_node() [text summary + metadata]
```

### Reference
- Theory of Constraints (Goldratt)
- Lean Six Sigma cost-of-quality framework
- `mayankysharma/langgraph-code-agent` — QA pipeline pattern

---

## Phase 5: Safety Audit & Human-in-the-Loop (Week 6)

**Goal:** Safety compliance analysis with incident-to-regulation matching and a human review gate for critical findings.

**Prerequisite:** `sentence-transformers` for local embeddings (no external API dependency).

---

### Step 5.0: State Models & Synthetic Data

Extend `state.py` and add synthetic data generators for safety test scenarios.

- [ ] **`SafetyFinding` model** — `station`, `hazard_type` (e.g., "lockout_tagout", "ppe_violation", "fall_hazard"), `osha_section` (e.g., "1910.147"), `severity` ("critical"|"high"|"medium"|"low"), `description`, `recommendation`, `score` (0-100)
- [ ] **`SafetyResult` model** — `overall_safety_score` (0-100), `compliance_rating` ("non_compliant"|"needs_improvement"|"compliant"|"excellent"), `findings` (list of SafetyFinding), `highest_risk_categories` (list), `data_points` (count of records analyzed)
- [ ] **`TimeStudyResult` model** — `station`, `mean_cycle_time`, `std_dev`, `min_cycle_time`, `max_cycle_time`, `num_observations`, `std_deviation_level` ("low"|"medium"|"high"), `normal_time`, `pfd_allowance`, `rated_time`
- [ ] **`tools/synthetic_data.py`** — Add `generate_safety_csv()` and `generate_time_study_csv()` generators with realistic safety incident and time observation data

**Tests:** State model serialization, synthetic data validation, model `to_dict()` methods.

---

### Step 5.1: OSHA Knowledge Base

Create a structured, searchable OSHA standards reference.

- [ ] **`data/osha_standards.md`** — Curated excerpt of relevant 29 CFR 1910 sections:
  - §1910.147 — Lockout/Tagout (LOTO)
  - §1910.132/133/134/136/137/138/148 — PPE (general, eye/face, head, foot, hand, electrical, hearing)
  - §1910.147 — Electrical safety
  - §1910.20 — Hearing conservation
  - §1910.38 — Emergency action plans
  - §1910.120 — Hazardous waste operations
  - §1910.178 — Powered industrial trucks
  - §1910.212 — Machine guarding
  - §1910.303 — Electrical standards
  - §1910.333 — Electrical safe work practices
  - §1910.132 — General PPE requirements
  - (Each section: requirement summary, applicable scenarios, penalties, key controls)
- [ ] **Chunking strategy** — Split into semantic chunks (~500 tokens) keyed by OSHA section number for retrieval

No code changes needed yet — this is a data file that Step 5.2 will consume.

---

### Step 5.2: OSHA RAG Tool

Build the retrieval engine using local sentence embeddings.

- [ ] **`src/tools/knowledge/__init__.py`** — Package init
- [ ] **`src/tools/knowledge/osha_rag.py`** — `OSHAKnowledgeBase` class:
  - Loads `data/osha_standards.md` on initialization
  - Chunks text by OSHA section header
  - Computes sentence embeddings via `sentence-transformers` (e.g., `all-MiniLM-L6-v2`, ~23MB, fast)
  - `search(query, top_k=3)` — returns matching OSHA sections with similarity scores
  - `get_recommendation(osha_section, hazard_type)` — deterministic recommendation lookup (maps OSHA section + hazard to standard control measures)
  - `assess_compliance(query)` — parses incident description → identifies hazard categories → matches to OSHA sections → returns compliance score and gaps
  - All computations local, no external API dependency
- [ ] **Embedding caching** — Pre-compute embeddings once, save to `data/osha_embeddings.json` to avoid recomputation

**Dependencies:** `sentence-transformers` (add to `requirements.txt` + `pyproject.toml`)
**Fallback:** If embeddings fail, fall back to keyword section matching (OSHA section numbers as keywords).

---

### Step 5.3: Safety Audit Node

Implement the safety analysis node that wires everything together.

- [ ] **`src/graph/nodes/safety_audit.py`** — `safety_audit_node(state)`:
  - Reads CSV data (incident/downtime data) or analyzes query text for safety keywords
  - Extracts hazard indicators: LOTO mentions, PPE mentions, electrical incidents, fall hazards, machine guarding references
  - Calls `OSHAKnowledgeBase.assess_compliance()` to generate findings
  - Returns structured result: `SafetyFinding` list, compliance score, recommendations
  - Sets `state.safety_result = SafetyResult(...)`
  - Sets `state.metadata.safety_findings_count` and `state.metadata.safety_score`
  - If `safety_score < 50`, sets `state.metadata.safety_critical = True` (triggers human review flag)
  - Handles missing data gracefully (returns partial findings with warning)

**Tests:** `safety_audit_node` runs with synthetic data, hazard type detection, OSHA section matching, compliance scoring, critical finding flag.

---

### Step 5.4: Time Study Node

Basic time study / cycle time analysis node.

- [ ] **`src/graph/nodes/time_study.py`** — `time_study_node(state)`:
  - Reads CSV and groups by station/machine
  - Calculates per-station: mean cycle time, std dev, min, max, observations
  - Applies PFD (Personal Fatigue/Delay) allowance (default 15%) and policy allowance (default 5%)
  - `std_deviation_level`: low (<10% CV), medium (10-20%), high (>20%)
  - Returns structured `TimeStudyResult` per station
  - Sets `state.time_study_result = TimeStudyResult(...)`
  - Identifies stations with high cycle time variability (potential quality risk)

**Tests:** `time_study_node` with synthetic data, PFD calculation, std deviation classification, high variability detection.

---

### Step 5.5: Graph Integration & Conditional Routing

Wire safety and time study into the workflow with conditional edges.

- [ ] **`analyze.py`** — Add `safety` and `time_study` to `ANALYSIS_HANDLERS`:
  ```python
  ANALYSIS_HANDLERS = {
      "oee": oee_analysis.oee_analysis_node,
      "bottleneck": bottleneck.bottleneck_node,
      "cost": cost_analysis.cost_node,
      "trend": trend_analysis.trend_analysis_node,
      "safety": safety_audit.safety_audit_node,       # NEW
      "time_study": time_study.time_study_node,       # NEW
  }
  ```
- [ ] **`response.py`** — Add safety formatting:
  - If `safety_result` present: append safety score, compliance rating, findings summary
  - If `time_study_result` present: append station cycle time table
  - If `safety_critical` flag: prepend warning banner
- [ ] **`workflow.py`** — Add conditional edges:
  - `workflow.add_conditional_edges("analyze", _safety_routing, {"human_review": "human_review", "continue": "response"})`
  - `_safety_routing(state)`: returns `"human_review"` if `safety_score < 50`, else `"continue"`
  - Add `human_review` node to graph (pending Step 5.6)

---

### Step 5.6: Human Review Gate

Implement the human-in-the-loop mechanism for critical safety findings.

- [ ] **`src/graph/nodes/human_review.py`** — `human_review_node(state)`:
  - Receives state with safety findings
  - CLI mode: prints findings, prompts user for `approve`/`reject`/`modify`
  - `approve`: passes findings through to response
  - `reject`: removes or downgrades findings, continues
  - `modify`: accepts user feedback, adjusts recommendations
  - Sets `state.metadata.review_status` and `state.metadata.review_decision`
  - In API mode (non-CLI): returns findings as `requires_review=True` with decision pending (API caller handles review)
- [ ] **Conditional edge wiring** — `human_review → response` after review decision
- [ ] **Non-blocking review** — For API/frontend use: safety-critical queries return `requires_review: true` in response; human reviews asynchronously via a separate endpoint (Phase 6)

**Tests:** Human review approval flow, rejection flow, CLI vs API mode detection, safety-critical routing decision.

---

### Step 5.7: Tests & Integration

Comprehensive test suite for Phase 5.

- [ ] **`tests/test_phase5.py`** — Target ~30 tests:
  - State model tests: SafetyFinding, SafetyResult, TimeStudyResult serialization
  - Synthetic data tests: safety CSV, time study CSV generators
  - OSHA RAG tests: knowledge base loading, chunking, search, compliance assessment
  - Safety node tests: hazard detection, OSHA matching, scoring, critical flag
  - Time study tests: cycle time stats, PFD calculation, variability classification
  - Human review tests: approval, rejection, CLI mode
  - Full pipeline: query → classify → router → analyze → (human_review?) → response
  - Edge cases: missing data, no safety keywords, critical findings with API mode

### Deliverables
- ✅ Safety compliance scoring with OSHA section matching
- ✅ Incident-to-regulation mapping (hazard type → OSHA section → recommendation)
- ✅ Human-in-the-loop gate for safety-critical findings (CLI + API modes)
- ✅ Time study / cycle time analysis with PFD allowances
- ✅ Local embedding-based RAG (no external API dependency)
- ✅ ~30 new tests (145+ total)

### Reference
- NVIDIA AI-Q checkpointing pattern (for pause/resume)
- Safety regulations: 29 CFR 1910 (general industry), 29 CFR 1926 (construction)
- `sentence-transformers` library (all-MiniLM-L6-v2 model)
- `langchain-ai/langgraph` — conditional edges and subgraph pattern

---

## Phase 6: Production Hardening (Week 7-8) ✅ COMPLETE

**Goal:** Polish, document, deploy as API service.
**Status:** Complete ✅ — 2026-07-31 (implemented before Phase 5; Phase 5 remains pending)

### Completed ✅
- [x] **6.0: PostgreSQL/SQLite Persistence Layer** ✅ — 2026-07-30
  - SQLAlchemy models: `Session`, `Query`, `AnalysisResult` (3-table cascade design)
  - Config module: `.env`-driven (`DATABASE_URL` env var, defaults to SQLite in `data/godinez.db`)
  - Repository pattern: `QueryRepository` (CRUD), `SessionRepository` (query history + summary), `AnalysisResultRepository` (result storage)
  - Alembic migration: `alembic.ini`, `alembic/env.py`, `alembic/versions/001_initial_schema.py`
  - Auto-initialized on API startup (non-fatal if DB unavailable)
  - `persist_query_result()` called after every successful API query
  - `get_session_summary()` returns count, intents, first/last query for a session
  - `get_session_history()` returns all queries sorted by timestamp (most recent first)
  - `get_result_by_query_id()` retrieves full result with metadata/charts/errors
  - Configurable: `DATABASE_URL="off"` disables persistence, `DATABASE_URL=sqlite:///...` for SQLite, `DATABASE_URL=postgresql://...` for PostgreSQL
  - **`requirements.txt`** updated with `alembic>=1.13.0`
  - **`alembic/`** directory created with full migration scaffolding

- [x] **6.1: API Route Updates for Persistence** ✅ — 2026-07-30
  - `POST /api/query` now persists results via `persist_query_result()`
  - `GET /api/results/{session_id}` returns full session history with metadata
  - `GET /api/persistence/status` reports enabled/disabled + DB type (sqlite/postgresql)
  - Error handling: non-fatal persistence failures (result still served, warning logged)
  - FastAPI `query_api()` function updated to accept and persist results

- [x] **6.2: Data Upload Endpoint** ✅ — 2026-07-31
  - `POST /api/data`, `GET /api/data/list`, `DELETE /api/data/{filename}`
  - `tests/test_data_api.py` — 21 tests (upload, list, delete, validation, security)

- [x] **6.3: FastAPI Server (existing routes)** ✅ — 2026-07-31
  - `POST /api/query`, `GET /api/results/{session_id}`, `GET /api/persistence/status`, `GET /health`

- [x] **6.4: Comprehensive Tests** ✅ — 2026-07-31
  - `tests/test_comprehensive.py` — 60 tests (OEE/CSV/bottleneck/cost edge cases, full API chain, multi-intent, error recovery, security)
  - `tests/test_persistence.py` — 26 tests (models, config, repositories, cascade delete, full pipeline)
  - `tests/test_cli.py` — 35 tests (parser, all 5 commands, config overrides)

- [x] **6.5: Configuration Management** ✅ — 2026-07-31
  - `src/config/` package: frozen `Config` dataclass, `Config.load()` with 4-level precedence
  - `tests/test_config.py` — 40 tests (defaults, JSON/env overrides, validation, backward compat)
  - `.env.example` with all 18 configurable env vars

### Deliverables
- ✅ SQLAlchemy models for Session/Query/AnalysisResult with cascade deletes
- ✅ Config module with .env-driven DATABASE_URL (SQLite/PostgreSQL/off)
- ✅ Repository pattern (QueryRepo, SessionRepo, ResultRepo)
- ✅ Alembic migration scaffolding (initial schema)
- ✅ API persistence integration (persist_query_result on every query)
- ✅ `GET /api/results/{session_id}` — retrieve past analyses
- ✅ `GET /api/persistence/status` — check persistence configuration
- ✅ `POST /api/query` — persists results + returns structured response
- ✅ CLI automatic persistence (when `DATABASE_URL` env var is set, no flag needed)
- ✅ README documentation (env vars, persistence setup, alembic commands)
- ✅ Planning.md updated with Phase 6 details

### Architecture
```
API Request → POST /api/query
  → API._run_query() [workflow execution]
  → persist_query_result() [QueryRepository.create + AnalysisResultRepository.create]
  → QueryResponse (with charts + metadata)

GET /api/results/{session_id}
  → QueryRepository.get_session_history(session_id)
  → returns [Query] + AnalysisResult with metadata/charts

GET /api/persistence/status
  → get_url() check
  → returns {enabled: true/false, database_type: "sqlite"/"postgresql"}

CLI: python main.py analyze "query" --session <id> --trace
  → workflow execution (in analyze command)
  → persist_query_result() [same persistence layer]
```

### Reference
- `langchain-ai/langgraph-persistence` — checkpoint pattern
- `sqlalchemy` ORM documentation — declarative models
- `alembic` migration guide — initial schema creation

---

## Phase 6.0: PostgreSQL Persistence (Phase 6 Sub-Phase 0) ✅ COMPLETE

**Goal:** Ensure results aren't lost between requests by using a proper database layer.

### Completed ✅
- [x] **SQLAlchemy Models** (`src/persistence/models.py`):
  - ✅ `Session` — session tracking (session_id, user_id, timestamps)
  - ✅ `Query` — individual queries (query_text, intent, confidence, timestamp)
  - ✅ `AnalysisResult` — full result (response, metadata, charts, errors)
  - Cascade deletes: session → queries → results
  - Foreign keys: `queries.session_id → sessions.session_id`, `results.query_id → queries.id`

- [x] **Configuration Module** (`src/persistence/config.py`):
  - ✅ `.env`-driven via `DATABASE_URL` environment variable
  - ✅ Default: SQLite at `data/godinez.db`
  - ✅ `get_engine()` — singleton engine with connection pooling
  - ✅ `get_session_factory()` — session factory
  - ✅ `init_db()` — creates tables on startup
  - ✅ `get_db_session()` — provides scoped session

- [x] **Repository Pattern** (`src/persistence/repositories.py`):
  - ✅ `QueryRepository` — CRUD operations for queries
  - ✅ `SessionRepository` — session creation, history, summary
  - ✅ `AnalysisResultRepository` — result persistence and retrieval
  - ✅ `persist_query_result()` — helper function (full pipeline)
  - ✅ `get_session_summary()` — session analytics
  - ✅ `get_session_history()` — chronological query list
  - ✅ `get_result_by_query_id()` — specific result lookup

- [x] **Alembic Migration** (`alembic/`):
  - ✅ `alembic.ini` — configuration file
  - ✅ `alembic/env.py` — migration runner with project metadata
  - ✅ `alembic/versions/001_initial_schema.py` — initial schema migration
  - ✅ Migration creates: sessions, queries, results tables
  - ✅ `requirements.txt` updated with `alembic>=1.13.0`

- [x] **API Integration** (`src/api/app.py`):
  - ✅ `POST /api/query` — persists results via `persist_query_result()`
  - ✅ `GET /api/results/{session_id}` — retrieves session history
  - ✅ `GET /api/persistence/status` — reports persistence configuration
  - ✅ Auto-initialized on startup (non-fatal if DB unavailable)

- [x] **CLI Integration** (`src/cli/commands/analyze.py`):
  - ✅ Persistence is automatic when `DATABASE_URL` env var is set (no `--persist` flag needed)
  - ✅ Same persistence layer as API (shared models + repositories)
  - ✅ Best-effort persistence — failures don't crash the CLI

- [x] **Test Suite** — ⚠️  `tests/test_persistence.py` was planned but never committed
  - 0 dedicated persistence tests exist
  - API integration tests cover basic query persistence flow

### Deliverables
- ✅ SQLAlchemy models for Session/Query/AnalysisResult
- ✅ Configuration module with .env-driven DATABASE_URL
- ✅ Repository pattern for clean database operations
- ✅ Alembic migration for schema versioning
- ✅ API persistence integration
- ✅ CLI automatic persistence (when `DATABASE_URL` is set)
- ✅ README documentation (env vars, persistence setup, alembic commands)

### Architecture
```
API Request → POST /api/query
  → _run_query() [workflow execution]
  → persist_query_result() [QueryRepo.create + AnalysisResultRepo.create]
  → QueryResponse (with charts + metadata)

GET /api/results/{session_id}
  → QueryRepo.get_session_history(session_id)
  → returns [Query] + AnalysisResult with metadata/charts

CLI: python main.py analyze "query" --session <id> --trace
  → workflow execution (analyze command builds & invokes graph directly)
  → persist_query_result() [same persistence layer]
```

### Reference
- SQLAlchemy ORM documentation — declarative models
- Alembic migration guide — initial schema creation
- LangSmith checkpointing pattern — result persistence strategy

---

## Phase 6: Production Hardening (Week 7-8) [CONTINUED]

### Completed ✅

#### Step 6.0: PostgreSQL / SQLite Persistence Layer ✅
- [x] SQLAlchemy models: `Session`, `Query`, `AnalysisResult` (3-table cascade design)
- [x] `Session` — session_id (UUID), user_id, created_at, updated_at
- [x] `Query` — query_text, intent, confidence (0-100 int), timestamp, session_id FK
- [x] `AnalysisResult` — response, intent, metadata JSON (`analysis_metadata` attr → `metadata` DB col), charts JSON, errors JSON, query_id FK
- [x] Configurable via `DATABASE_URL` env var: `sqlite:///...` (default), `postgresql://...`, `off`
- [x] Alembic migration scaffolding (`alembic/`, `alembic.ini`, `alembic/versions/001_initial_schema.py`)
- [x] Repository pattern (`src/persistence/repositories.py`): `create_session`, `save_query`, `save_result`, `persist_query_result`, `get_session_summary`, `get_results_by_session`
- [x] `POST /api/query` persists result on every successful query
- [x] `GET /api/results/{session_id}` returns all queries + full result (response, metadata, charts, errors)
- [x] `persistence/models.py` `Session.queries` — `cascade="all, delete-orphan"` (ORM-level cascade)

#### Step 6.1: CLI Subcommands ✅
- [x] `python main.py analyze "query"` — runs workflow, prints result, persists to DB if configured
  - Flags: `--session <id>`, `--trace`
- [x] `python main.py report --session <id>` — generates formatted report from past session
  - Flags: `--format text|json`, `--file <path>`
- [x] `python main.py data --list` — lists all CSVs in data/ with record counts and machine IDs
- [x] `python main.py data --file <csv> --type production` — validates and imports CSV to data/
  - Flag: `--overwrite`
- [x] `python main.py config --show` — prints current configuration (LLM, OEE thresholds, storage)
- [x] `python main.py config set <key> <value>` — writes to `.godinez_config.json`, applied on next startup
  - `config set oee_thresholds.critical 60` — adjusts OEE classification thresholds
  - `config set database.url postgresql://...` — changes database (accepts sqlite:///, postgresql://, off)
- [x] `python main.py server` — starts FastAPI via uvicorn (`--host`, `--port`, `--reload`)
- [x] `main.py` (root) — thin wrapper delegating to `src.cli.main.main()` (no duplication)
- [x] `src/config.py` reads `.godinez_config.json` at import time to apply threshold/LLM overrides
- [x] `tests/test_cli.py` — 35 tests: parser, all 5 commands, config overrides

#### Step 6.2: Data Upload Endpoint ✅
- [x] `POST /api/data` — upload production CSV; validates extension, required columns, size (50 MB); saves with timestamped filename; returns row_count, columns, date_range, machine_ids
- [x] `GET /api/data/list` — lists all CSVs in data/ with best-effort metadata; ignores non-CSV files
- [x] `DELETE /api/data/{filename}` — removes dataset; rejects path traversal attempts
- [x] Reuses `src/tools/csv_reader.py` for all parsing (no duplicate logic)
- [x] `python-multipart>=0.0.9` added to `requirements.txt`
- [x] Routes in `src/api/data_routes.py` (APIRouter, included in app.py)
- [x] `tests/test_data_api.py` — 21 tests: upload, list, delete, validation, security

#### Step 6.3: FastAPI Server (existing routes) ✅
- [x] `POST /api/query` — run agent with query + persistence
- [x] `GET /api/results/{session_id}` — retrieve past analyses (full result including response/charts)
- [x] `GET /api/persistence/status` — check persistence configuration
- [x] `GET /health` — health check with version + tracing status

#### Step 6.4: Comprehensive Tests ✅
- [x] `tests/test_comprehensive.py` — 60 tests filling production-critical gaps
- [x] **Unit — OEE Calculator edge cases** (10 tests): zero planned time, good_count > total, actual_run > planned, negative downtime, 10 000-record aggregation, single-record average, empty average, rating boundary, recommendation present, zero ideal cycle time
- [x] **Unit — CSV Reader edge cases** (8 tests): file not found, missing required column, all malformed rows raise, malformed rows skipped, headers-only raises, multiple machines extracted, date range correct, 1 000-row parse
- [x] **Unit — Bottleneck Detector edge cases** (6 tests): all-zero cycle times, zero planned time, many stations finds highest CT, identical cycle times → low severity, missing columns default to zero, 500-record large dataset
- [x] **Unit — Cost Estimator edge cases** (7 tests): zero production, zero downtime, perfect quality zero scrap, custom cost params, large dataset sums correctly, pareto ordering, ROI projection exists
- [x] **Integration — Full API chain** (5 tests): upload→list shows file, upload→delete removes file, query→results with in-memory persistence, query response has required fields, results without persistence returns empty
- [x] **Integration — Multi-intent routing** (7 tests): OEE/bottleneck/cost/trend/safety keyword routing, unknown query low confidence, full workflow E2E with mocked classify
- [x] **Integration — Error recovery** (8 tests): LLM unavailable → 500 not crash, workflow invoke exception → 500, invalid CSV upload → 400 not 500, health always responds, missing query → 422, query too long → 422, nonexistent session, persistence failure non-fatal
- [x] **Security** (9 tests): SQL injection in session_id, SQL injection in query body (echoed safely), XSS in query not executed, path traversal in DELETE (%2F), path traversal (backslash), subpath blocked, 50 MB limit enforced, empty upload rejected, non-CSV extension rejected

#### Step 6.5: Configuration Management ✅
- [x] `src/config/` package replaces flat `src/config.py` (all existing imports unchanged)
- [x] `src/config/loader.py` — frozen `Config` dataclass with six typed sections: `database`, `llm`, `oee`, `bottleneck`, `cost`, `graph`
- [x] `Config.load()` classmethod — load order: defaults → `.godinez_config.json` → `CONFIG_FILE` env var → individual env vars
- [x] `Config.load(_config_path=...)` — optional override for testing (no monkeypatching of module paths needed)
- [x] Validation at load time with clear errors: temperature (0–2), OEE thresholds (strictly ascending), graph iterations/timeout (>= 1)
- [x] `src/config/__init__.py` — exports `Config`, `config` (loaded instance), path constants, and backward-compat flat names (`LLM_MODEL`, `OEE_THRESHOLDS`, `MAX_ITERATIONS`, `GRAPH_TIMEOUT`)
- [x] `_CONFIG_FILE` / `_load_json_config()` preserved for test_cli.py backward compat
- [x] `src/tools/analysis/bottleneck_detector.py` — `SEVERITY_THRESHOLDS` class variable now reads from `config.bottleneck`
- [x] `src/tools/analysis/cost_estimator.py` — `DEFAULT_COSTS` class variable now reads from `config.cost`
- [x] `.env.example` — all configurable env vars with documentation and safe defaults
- [x] `tests/test_config.py` — 40 tests: defaults, JSON overrides, CONFIG_FILE env var, individual env vars, validation errors, frozen immutability, backward-compat imports

#### Other ✅
- [x] Comprehensive test suite: 297 tests (297 passing)
- [x] README: setup guide, usage examples, configuration reference, architecture diagram
- [x] Sample production data for demo
- [x] Code review + cleanup:
  - `src/graph/nodes/cost_analysis.py` — refactored to delegate to `CostEstimator` engine
  - `src/tools/csv_reader.py` — added `CsvReader` OOP wrapper class
  - `main.py` — thin wrapper delegating to `src.cli.main.main()`

### Known Issues (all resolved ✅)
- [x] `test_main_run_query_returns_metrics` — renamed to `test_workflow_returns_metrics`, rewritten to call `build_workflow()` + `compiled.invoke()` directly
- [x] `src/api/app.py get_results()` — fixed: `result_items` undefined; fixed `query_id` type (`str` → `int`); added missing `session_id`; now includes `response`/`metadata`/`charts`/`errors`
- [x] `test_persistence.py` — written: 26 tests covering models, config, repositories, full pipeline
- [x] `trend_engine.py:351` divide-by-zero — fixed: added `else` so `z_score` from `std == 0` path is not overwritten
- [x] FastAPI `@app.on_event` deprecated — replaced with `@asynccontextmanager` lifespan
- [x] `httpx` / `starlette.testclient` deprecation — `httpx2>=2.9.0` installed, added to `requirements.txt`
- [x] `main.py.bak` — deleted
- [x] `persistence/models.py` `Session.queries` — added `cascade="all, delete-orphan"`
- [x] `AnalysisResult.analysis_metadata` column name mismatch — `Column("metadata", JSON)` explicit name; `save_result()` uses `analysis_metadata=` kwarg; metadata now persisted correctly
- [x] `report.py` metadata — `q.result.metadata` → `q.result.analysis_metadata`
- [x] `config set` positional syntax — changed from `--set KEY VALUE` flag to `config set KEY VALUE` positional (matches spec)
- [x] `config set database.url` validation — was `postgresql://` only, now accepts any URL (`sqlite:///`, `postgresql://`, `off`)
- [x] `main.py` duplication — root `main.py` was a full copy of `src/cli/main.py` with a wrong `sys.path`; now a 10-line thin wrapper

---

## Current File Structure

```
godinez-industrial-engineer/
├── src/
│   ├── cli/
│   │   ├── main.py                  # Argparse CLI entry point (5 subcommands)
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── analyze.py           # analyze subcommand: workflow build + run + output
│   │       ├── report.py            # report subcommand: session report generation
│   │       ├── data.py              # data subcommand: list/import datasets
│   │       ├── config.py            # config subcommand: show/edit settings
│   │       └── server.py            # server subcommand: uvicorn FastAPI server
│   ├── graph/
│   │   ├── __init__.py              # Exports: build_workflow, GodinezState
│   │   ├── state.py                 # Pydantic GodinezState + result models (Bottleneck, Cost, etc.)
│   │   ├── workflow.py              # StateGraph compilation: intake → classify → router → analyze → response → END
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── intake.py            # Query validation + timestamp
│   │       ├── classify.py          # LLM intent classification (3-tier fallback)
│   │       ├── router.py            # Keyword-based intent routing
│   │       ├── analyze.py           # Orchestrator → dispatches to ANALYSIS_HANDLERS
│   │       ├── response.py          # Formatted response + chart embedding
│   │       ├── oee_analysis.py      # OEE calculation + reporting
│   │       ├── bottleneck.py        # Constraint detection node
│   │       ├── cost_analysis.py     # Scrap/rework/waste cost estimation node
│   │       └── trend_analysis.py    # Statistical trends + forecasting node
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── analysis/
│   │   │   ├── __init__.py
│   │   │   ├── bottleneck_detector.py  # BottleneckDetector.analyze()
│   │   │   ├── cost_estimator.py       # CostEstimator.analyze()
│   │   │   └── trend_engine.py         # Trend analysis, anomaly, forecasting
│   │   ├── chart_generator.py      # matplotlib chart creation
│   │   ├── chart_templates.py      # OEE trend, Pareto, control charts
│   │   ├── chart_palette.py        # Centralized color scheme
│   │   ├── csv_reader.py           # CSV parsing + filters + CsvReader OOP wrapper
│   │   ├── oee_calculator.py       # Deterministic OEE math
│   │   └── synthetic_data.py       # Production + bottleneck + cost data generators
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── logger.py            # Structured JSON logging
│   │   ├── tracing.py           # LangSmith integration
│   │   └── metrics.py           # Execution metrics
│   ├── persistence/             # Phase 6.0 persistence layer
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy Session, Query, AnalysisResult
│   │   ├── config.py            # DATABASE_URL config, engine, session factory
│   │   └── repositories.py      # QueryRepo, SessionRepo, ResultRepo
│   ├── api/
│   │   ├── app.py               # FastAPI REST API (POST/GET /api/query, GET /api/results, GET /health)
│   │   └── data_routes.py       # Data upload router (POST/GET/DELETE /api/data)
│   └── config/                  # Configuration package (Step 6.5)
│       ├── __init__.py          # Exports Config, config instance, backward-compat flat names
│       └── loader.py            # Frozen Config dataclass + Config.load() with validation
├── data/
│   ├── sample_production.csv    # Demo data (84 shifts)
│   ├── synthetic_production.csv # Synthetic data for testing
│   └── godinez.db               # SQLite database (auto-created, not committed)
├── alembic/                     # Alembic migrations
│   ├── env.py                   # Migration runner
│   └── versions/
│       └── 001_initial_schema.py # Initial schema migration
├── alembic.ini                  # Alembic configuration (root-level)
├── tests/
│   ├── conftest.py              # LLM mocks + fixtures
│   ├── test_workflow.py         # 40 tests (graph + nodes + CLI integration)
│   ├── test_observability.py    # 20 tests (logging, tracing, metrics)
│   ├── test_api.py              # 12 tests (FastAPI endpoints)
│   ├── test_trend_engine.py     # 18 tests (trend analysis + anomaly detection)
│   ├── test_phase4.py           # 25 tests (bottleneck + cost + state models)
│   ├── test_persistence.py      # 26 tests (models, config, repositories, pipeline)
│   ├── test_cli.py              # 35 tests (parser, all 5 commands, config overrides)
│   ├── test_data_api.py         # 21 tests (upload, list, delete, validation, path traversal)
│   ├── test_config.py           # 40 tests (defaults, JSON/env overrides, validation, backward compat)
│   └── test_comprehensive.py    # 60 tests (OEE/CSV/bottleneck/cost edge cases, integration chain, security)
├── main.py                      # Root CLI entry point (thin wrapper → src.cli.main.main)
├── .env.example                 # All configurable env vars with safe defaults (committed)
├── .godinez_config.json         # Runtime config (DB URL, thresholds — not committed)
├── alembic.ini                  # Alembic configuration
├── pyproject.toml
├── requirements.txt
├── README.md
└── .gitignore
```

**Commit state (as of 2026-07-31, last commit = `bfb91bf`):** All Phase 6 files committed.

**Planned Phase 5 additions (not started):**
- `src/tools/knowledge/osha_rag.py` — OSHA RAG tool
- `src/graph/nodes/safety_audit.py` — Safety audit node
- `src/graph/nodes/time_study.py` — Time study node
- `src/graph/nodes/human_review.py` — Human review node
- `data/osha_standards.md` — OSHA reference knowledge base

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Factory data inaccessible (no API/SQL) | High | High | Start with CSV imports, add connectors later |
| LLM hallucination in analysis | Medium | High | Keep calculators deterministic (pandas/math), use LLM only for routing/synthesis |
| Scope creep (too many analysis types) | Medium | Medium | Stick to Phase 1-3 before expanding |
| Performance with large datasets | Low | Medium | Chunk processing, cache results |
| Safety regulation accuracy | Medium | Critical | Always flag as "informational, not legal advice"; human review mandatory |
| Embedding model dependencies | Medium | Low | Use lightweight model (MiniLM-L6-v2, ~23MB); fallback to keyword matching |
| Human review UX complexity | Medium | Medium | Non-blocking API mode (Phase 6) for async review |

---

## Success Criteria

- [x] Agent processes natural language queries about manufacturing data
- [x] OEE calculation is accurate and verifiable (deterministic, no LLM dependency)
- [x] Trends are detected and forecasted with confidence intervals
- [x] Bottlenecks are identified with clear reasoning and severity ratings
- [x] Cost analysis with waste breakdown (scrap, rework, downtime) and ROI projections
- [x] Reports are generated in professional format with embedded charts
- [ ] Safety findings require human approval
- [x] Code is testable and documented (115/115 tests passing)
- [x] Runs on DGX locally (no external API dependency for core analysis)
- [x] Results persist across API requests (SQLite/PostgreSQL)
- [x] Session history retrievable via REST API

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

### 2026-07-30: PostgreSQL/SQLite Persistence Layer (Phase 6.0)
**Decision:** Use SQLAlchemy declarative models with Alembic migrations for database persistence. Support both SQLite (default) and PostgreSQL via `DATABASE_URL` environment variable.
**Reasoning:**
- Results must persist across API requests — in-memory state is lost between calls
- SQLite provides zero-config persistence for development/demo
- PostgreSQL enables production scalability with concurrent access
- Repository pattern provides clean separation of concerns
- Alembic ensures schema versioning and migration safety

**Architecture:**
```
Session (session_id, user_id, timestamps)
  └── Query (query_text, intent, confidence, timestamp)
        └── AnalysisResult (response, metadata, charts, errors)
```
Cascade deletes: session → queries → results. Foreign keys enforce referential integrity.

**Implementation:**
- `src/persistence/models.py` — SQLAlchemy declarative models
- `src/persistence/config.py` — DATABASE_URL config, engine, session factory
- `src/persistence/repositories.py` — QueryRepo, SessionRepo, ResultRepo (CRUD operations)
- `alembic/` — Migration scaffolding with initial schema
- API: `persist_query_result()` called after every successful query
- CLI: persistence is automatic when `DATABASE_URL` env var is set (no flag needed)

**Configuration:**
- `DATABASE_URL="off"` → persistence disabled
- `DATABASE_URL=sqlite:///data/godinez.db` → SQLite (default)
- `DATABASE_URL=postgresql://user:pass@localhost/godinez` → PostgreSQL

**Trade-off:** Adds database complexity, but provides essential persistence for production use. SQLite is zero-config; PostgreSQL requires separate deployment.

**Reference:**
- SQLAlchemy ORM documentation — declarative models
- Alembic migration guide — schema versioning
- LangSmith checkpointing pattern — result persistence strategy
- Repository pattern (Martin Fowler) — clean database abstraction

### 2026-07-30: Alembic Migration Strategy
**Decision:** Use Alembic for all schema migrations, starting with initial schema migration.
**Reasoning:** Ensures schema versioning, migration history, and safe upgrades. Critical for production deployments where database schema changes must be coordinated.

**Commands:**
```bash
# Upgrade to latest migration
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1
```

**Trade-off:** Adds `alembic` dependency and migration workflow, but provides essential schema versioning for production.
