# Godínez IndustrialEngineer

AI-powered manufacturing analysis agent. Ask questions about your production data in plain English — get OEE scores, bottleneck detection, cost analysis, and trend forecasts back as structured reports.

Built on LangGraph multi-agent orchestration with a FastAPI REST layer, SQLite/PostgreSQL persistence, and a full CLI.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Setup Guide](#setup-guide)
4. [Usage — CLI](#usage--cli)
5. [Usage — REST API](#usage--rest-api)
6. [Usage — Docker](#usage--docker)
7. [Configuration Reference](#configuration-reference)
8. [API Reference](#api-reference)
9. [Troubleshooting](#troubleshooting)
10. [Contributing](#contributing)

---

## Quick Start

```bash
git clone https://github.com/your-org/godinez-industrial-engineer
cd godinez-industrial-engineer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Add your OPENAI_API_KEY
python main.py analyze "What is our OEE for last week?"
```

---

## Architecture

### Graph pipeline

Every query flows through the same LangGraph `StateGraph`:

```
User query
    │
    ▼
┌─────────┐     ┌──────────┐     ┌────────┐     ┌─────────┐     ┌──────────┐
│  intake │────▶│ classify │────▶│ router │────▶│ analyze │────▶│ response │
└─────────┘     └──────────┘     └────────┘     └─────────┘     └──────────┘
                     │                                │
                3-tier fallback              dispatch by intent
                1. vLLM (DGX)               ┌─ oee_analysis
                2. Ollama (local)            ├─ bottleneck
                3. keyword match             ├─ cost_analysis
                                             └─ trend_analysis
```

**Node responsibilities:**

| Node | What it does |
|------|-------------|
| `intake` | Validates query, adds timestamp, rejects empty input |
| `classify` | LLM intent classification → `oee` / `bottleneck` / `cost` / `trend` / `safety` / `general` |
| `router` | Keyword fallback routing when LLM unavailable |
| `analyze` | Dispatches to the right analysis handler(s); supports multi-intent chaining |
| `response` | Formats markdown report, embeds base64 charts |

### Data flow

```
CSV file ──┐
           ▼
    POST /api/data          GET /api/data/list
    data/{name}_{ts}.csv ──────────────────────▶ metadata
           │
           ▼
    POST /api/query ──▶ LangGraph pipeline ──▶ analysis result
                                  │
                                  ▼
                         SQLite / PostgreSQL
                                  │
                                  ▼
                    GET /api/results/{session_id}
```

### Source layout

```
src/
├── api/
│   ├── app.py           # FastAPI app + /api/query, /api/results, /health
│   └── data_routes.py   # /api/data upload/list/delete
├── cli/
│   ├── main.py          # argparse entry point (5 subcommands)
│   └── commands/        # analyze, report, data, config, server
├── config/
│   ├── __init__.py      # Loaded Config singleton + backward-compat names
│   └── loader.py        # Frozen Config dataclass, Config.load()
├── graph/
│   ├── state.py         # GodinezState (Pydantic)
│   ├── workflow.py      # StateGraph wiring + observability context
│   └── nodes/           # intake, classify, router, analyze, response, oee_analysis,
│                        # bottleneck, cost_analysis, trend_analysis
├── persistence/
│   ├── models.py        # SQLAlchemy: Session, Query, AnalysisResult
│   ├── config.py        # DATABASE_URL → engine singleton
│   └── repositories.py  # QueryRepo, SessionRepo, ResultRepo
└── tools/
    ├── analysis/        # BottleneckDetector, CostEstimator, TrendEngine
    ├── oee_calculator.py
    ├── csv_reader.py
    └── chart_generator.py
```

---

## Setup Guide

### 1. Prerequisites

- Python 3.10+
- An OpenAI API key (`OPENAI_API_KEY`)
- Optional: PostgreSQL for production persistence

### 2. Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` — the only required value is your API key:

```env
OPENAI_API_KEY=sk-...
```

All other values have safe defaults (SQLite persistence off, `gpt-4o-mini`, standard OEE thresholds).

### 4. Optional: enable persistence

```env
DATABASE_URL=sqlite:///data/godinez.db
```

On first run the database and tables are created automatically. For PostgreSQL:

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/godinez
```

Then run migrations once:

```bash
alembic upgrade head
```

### 5. Verify

```bash
python main.py analyze "Quick sanity check"
# Expected: intent=general, short response, no errors
```

---

## Usage — CLI

```
python main.py <subcommand> [options]
```

### `analyze` — run a query

```bash
python main.py analyze "What is our OEE for machine M1?"
python main.py analyze "Where is our bottleneck?" --session my-shift-A
python main.py analyze "Show cost breakdown for last week" --trace   # LangSmith tracing
```

**Expected output:**

```
OEE Analysis Report
==================================================
Date Range: 2024-01-01 to 2024-01-14
Shifts Analyzed: 84

Overall OEE: 86.1%  [Good]

  Availability: 86.1%
  Performance:  100.0%
  Quality:      100.0%

Recommendation: Focus on reducing downtime ...
```

### `report` — retrieve a past session

```bash
python main.py report --session my-shift-A
python main.py report --session my-shift-A --format json
python main.py report --session my-shift-A --format json --file report.json
```

### `data` — manage datasets

```bash
# List all CSVs in data/
python main.py data --list

# Import a production CSV
python main.py data --file /path/to/production.csv --type production
python main.py data --file /path/to/production.csv --type production --overwrite
```

Your CSV must have these columns: `date`, `shift`, `machine_id`, `planned_minutes`, `actual_run_minutes`, `downtime_minutes`, `ideal_cycle_time_seconds`, `total_count`, `good_count`, `downtime_reason`.

### `config` — view and set configuration

```bash
# Show current config
python main.py config --show

# Set a value (written to .godinez_config.json, applied on next start)
python main.py config set llm.model gpt-4o
python main.py config set llm.temperature 0.2
python main.py config set oee_thresholds.critical 55
python main.py config set database.url sqlite:///data/godinez.db
```

### `server` — start the REST API

```bash
python main.py server
python main.py server --host 0.0.0.0 --port 8080
python main.py server --reload    # dev mode
```

---

## Usage — REST API

### Start the server

```bash
python main.py server
# or
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Interactive docs at `http://localhost:8000/docs`.

### Run a query

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our OEE today?", "session_id": "shift-A-2024"}'
```

**Response:**

```json
{
  "query": "What is our OEE today?",
  "response": "**OEE Analysis Report**\n\nOverall OEE Score: 86.1% [Good]...",
  "intent": "oee",
  "session_id": "shift-A-2024",
  "metadata": {"oee_score": 86.1, "oee_rating": "good", "data_points": 84},
  "execution_summary": {"total_latency_ms": 1240},
  "success": true
}
```

### Upload a dataset

```bash
curl -X POST http://localhost:8000/api/data \
  -F "file=@production.csv"
```

```json
{
  "filename": "production_20240115_143022.csv",
  "saved_path": "/app/data/production_20240115_143022.csv",
  "size_bytes": 12840,
  "row_count": 84,
  "date_range": ["2024-01-01", "2024-01-14"],
  "machine_ids": ["M1", "M2", "M3"]
}
```

---

## Usage — Docker

### Single-container (SQLite)

```bash
docker build -t godinez .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e DATABASE_URL=sqlite:///data/godinez.db \
  -v $(pwd)/data:/app/data \
  godinez
```

### Full stack (PostgreSQL + app)

```bash
cp .env.example .env   # set OPENAI_API_KEY
docker compose up
```

Services:
- **app** → `http://localhost:8000`
- **db** → PostgreSQL 15 on port 5432 (internal)

The app waits for PostgreSQL to be healthy, then runs `alembic upgrade head` automatically before accepting requests.

### With Redis cache (optional)

```bash
docker compose --profile cache up
```

### Useful compose commands

```bash
docker compose logs -f app          # tail app logs
docker compose exec app bash        # shell into container
docker compose down -v              # stop and remove volumes
docker compose build --no-cache     # force rebuild
```

---

## Configuration Reference

Configuration is loaded in this precedence order (highest wins):

```
defaults → .godinez_config.json → CONFIG_FILE env var → individual env vars
```

### Environment variables

#### LLM

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required.** OpenAI API key |
| `LLM_MODEL` | `gpt-4o-mini` | Model name passed to ChatOpenAI |
| `LLM_TEMPERATURE` | `0.0` | Sampling temperature. Range: 0.0–2.0 |

#### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `off` | `off` disables persistence. `sqlite:///data/godinez.db` for SQLite. `postgresql://user:pass@host:5432/db` for PostgreSQL |

#### OEE Thresholds (%)

Must be strictly ascending: `critical < needs_improvement < good < world_class`.

| Variable | Default | Description |
|----------|---------|-------------|
| `OEE_CRITICAL` | `60.0` | Below this → "critical" rating |
| `OEE_NEEDS_IMPROVEMENT` | `75.0` | Below this → "needs_improvement" |
| `OEE_GOOD` | `85.0` | Below this → "good" |
| `OEE_WORLD_CLASS` | `90.0` | At or above → "world_class" |

#### Bottleneck Detection (balance delay %)

| Variable | Default | Description |
|----------|---------|-------------|
| `BOTTLENECK_CRITICAL` | `30` | Balance delay % → critical severity |
| `BOTTLENECK_HIGH` | `20` | Balance delay % → high severity |
| `BOTTLENECK_MEDIUM` | `10` | Balance delay % → medium severity |

#### Cost Defaults (USD)

| Variable | Default | Description |
|----------|---------|-------------|
| `COST_SCRAP_PER_UNIT` | `25.00` | Cost per scrapped unit |
| `COST_REWORK_PER_HOUR` | `45.00` | Labor cost per rework hour |
| `COST_DOWNTIME_PER_HOUR` | `150.00` | Cost per hour of unplanned downtime |
| `COST_DEFECT_PER_UNIT` | `5.00` | Quality loss per defect |

#### Graph Execution

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_ITERATIONS` | `10` | Max LangGraph node iterations |
| `GRAPH_TIMEOUT` | `120` | Workflow timeout in seconds |

#### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGSMITH_API_KEY` | — | Enables LangSmith tracing when set |
| `LANGCHAIN_TRACING_V2` | `false` | Set `true` to enable tracing |
| `LANGCHAIN_PROJECT` | `godinez-industrial-engineer` | LangSmith project name |

#### Docker / Server

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | uvicorn listen port |
| `WORKERS` | `2` | uvicorn worker processes (capped to 1 for SQLite) |
| `LOG_LEVEL` | `info` | uvicorn log level (`debug`/`info`/`warning`/`error`) |
| `CONFIG_FILE` | — | Path to a JSON config file that overrides `.godinez_config.json` |

### JSON config file (`.godinez_config.json`)

The CLI `config set` command writes here. You can also edit it directly:

```json
{
  "llm": {
    "model": "gpt-4o",
    "temperature": 0.1
  },
  "oee_thresholds": {
    "critical": 55.0,
    "needs_improvement": 70.0,
    "good": 83.0,
    "world_class": 92.0
  },
  "bottleneck": {
    "severity_critical": 35,
    "severity_high": 22,
    "severity_medium": 12
  },
  "cost": {
    "scrap_per_unit": 30.0,
    "rework_per_hour": 50.0,
    "downtime_per_hour": 200.0,
    "defect_per_unit": 8.0
  },
  "database": {
    "url": "postgresql://user:pass@localhost:5432/godinez"
  }
}
```

---

## API Reference

Base URL: `http://localhost:8000`

Interactive docs: `GET /docs` (Swagger UI) or `GET /redoc`

### `POST /api/query`

Run an analysis query through the agent pipeline.

**Request body:**

```json
{
  "query": "string (1–2000 chars, required)",
  "user_id": "string (optional)",
  "session_id": "string (optional — generated if omitted)",
  "enable_tracing": false
}
```

**Response `200`:**

```json
{
  "query": "What is our OEE?",
  "response": "**OEE Analysis Report**\n...",
  "intent": "oee",
  "session_id": "uuid",
  "user_id": null,
  "metadata": {"oee_score": 86.1, "oee_rating": "good", "data_points": 84},
  "execution_summary": {"total_latency_ms": 1240, "execution_order": ["intake","classify","router","analyze","response"]},
  "charts": null,
  "success": true
}
```

`charts` is a list of `{"type": "...", "data": "<base64 PNG>"}` objects for trend queries.

**Response `422`:** query missing or > 2000 chars  
**Response `500`:** internal error (LLM unavailable, etc.) — body contains `{"detail": {"error": "..."}}`

---

### `GET /api/results/{session_id}`

Retrieve all past queries and results for a session.

```bash
curl http://localhost:8000/api/results/shift-A-2024
```

**Response `200`:**

```json
{
  "session_id": "shift-A-2024",
  "query_count": 3,
  "intents": ["oee", "bottleneck", "cost"],
  "first_query": "What is our OEE?",
  "last_query": "Show cost breakdown",
  "queries": [
    {
      "query_id": 1,
      "query_text": "What is our OEE?",
      "intent": "oee",
      "confidence": 0.95,
      "timestamp": "2024-01-15T14:30:22",
      "response": "**OEE Analysis Report**...",
      "metadata": {"oee_score": 86.1},
      "session_id": "shift-A-2024"
    }
  ]
}
```

Returns empty `queries: []` when persistence is disabled (`DATABASE_URL=off`).

---

### `POST /api/data`

Upload a production CSV. Max 50 MB.

```bash
curl -X POST http://localhost:8000/api/data \
  -F "file=@production.csv"
```

**Required CSV columns:** `date`, `shift`, `machine_id`, `planned_minutes`, `actual_run_minutes`, `downtime_minutes`, `ideal_cycle_time_seconds`, `total_count`, `good_count`, `downtime_reason`

**Response `200`:**

```json
{
  "filename": "production_20240115_143022.csv",
  "saved_path": "/app/data/production_20240115_143022.csv",
  "size_bytes": 12840,
  "row_count": 84,
  "columns": ["date", "shift", "machine_id", ...],
  "date_range": ["2024-01-01", "2024-01-14"],
  "machine_ids": ["M1", "M2", "M3"]
}
```

**Response `400`:** not a CSV, missing columns, empty file  
**Response `413`:** file exceeds 50 MB

---

### `GET /api/data/list`

List all uploaded datasets.

```bash
curl http://localhost:8000/api/data/list
```

**Response `200`:**

```json
{
  "datasets": [
    {
      "filename": "production_20240115_143022.csv",
      "size_bytes": 12840,
      "row_count": 84,
      "date_range": ["2024-01-01", "2024-01-14"],
      "machine_ids": ["M1", "M2", "M3"]
    }
  ],
  "total": 1
}
```

---

### `DELETE /api/data/{filename}`

Delete a dataset.

```bash
curl -X DELETE http://localhost:8000/api/data/production_20240115_143022.csv
```

**Response `200`:** `{"success": true, "filename": "production_20240115_143022.csv"}`  
**Response `400`:** filename contains path separators  
**Response `404`:** file not found

---

### `GET /health`

```bash
curl http://localhost:8000/health
```

```json
{"status": "healthy", "version": "0.6.0", "tracing_enabled": false}
```

---

### `GET /api/persistence/status`

```bash
curl http://localhost:8000/api/persistence/status
```

```json
{"enabled": true, "database_type": "sqlite"}
```

---

## Troubleshooting

### `OPENAI_API_KEY` not set

```
openai.AuthenticationError: No API key provided
```

**Fix:** Add `OPENAI_API_KEY=sk-...` to your `.env` file and restart.

---

### CSV missing required columns

```
ValueError: Missing required columns: actual_run_minutes, downtime_minutes
```

**Fix:** Your CSV must include all 10 columns. Check the column names — they must match exactly (snake_case, no spaces).

---

### Database not available

```
⚠️ Persistence init failed (database may not be configured): ...
```

This is non-fatal — the API still serves results; they just aren't persisted. To enable persistence:

```env
DATABASE_URL=sqlite:///data/godinez.db
```

For PostgreSQL, run `alembic upgrade head` after setting `DATABASE_URL`.

---

### Alembic migration error

```
alembic.util.exc.CommandError: Can't locate revision identified by ...
```

**Fix:** The database schema is ahead of your migration files.

```bash
alembic stamp head    # mark current state as up-to-date
alembic upgrade head  # re-run
```

---

### Docker: `OPENAI_API_KEY is required`

The compose file uses `${OPENAI_API_KEY:?...}` which fails if the variable is unset.

**Fix:**

```bash
export OPENAI_API_KEY=sk-...
docker compose up
# or
echo "OPENAI_API_KEY=sk-..." >> .env
docker compose up
```

---

### Port already in use

```
OSError: [Errno 98] Address already in use
```

**Fix:** Kill the existing process or use a different port:

```bash
lsof -ti:8000 | xargs kill   # kill whatever is on 8000
python main.py server --port 8001
```

---

### LLM classification falls back to keyword matching

This is expected behaviour when neither the DGX vLLM server nor local Ollama is reachable. The keyword fallback handles all main intents (`oee`, `bottleneck`, `cost`, `trend`, `safety`) correctly for typical queries.

To use OpenAI classification directly, the router will use `gpt-4o-mini` automatically when the local servers are unreachable.

---

## Contributing

### Running tests

```bash
pip install -r requirements.txt
pytest                          # all 297 tests
pytest tests/test_workflow.py   # single file
pytest -k "oee"                 # filter by name
pytest --tb=short -q            # compact output
```

Tests mock all LLM calls (via `conftest.py` keyword fallback) — no API key needed to run the suite.

### Adding a new analysis node

1. **Create the engine** in `src/tools/analysis/my_engine.py`:

   ```python
   from dataclasses import dataclass, field

   @dataclass
   class MyResult:
       score: float = 0.0
       findings: list = field(default_factory=list)

       def to_dict(self) -> dict:
           return {"score": self.score, "findings": self.findings}

   class MyAnalyzer:
       @classmethod
       def analyze(cls, data: list[dict]) -> MyResult:
           ...
   ```

2. **Create the graph node** in `src/graph/nodes/my_analysis.py`:

   ```python
   from src.tools.csv_reader import read_production_csv
   from src.tools.analysis.my_engine import MyAnalyzer
   from src.config import DATA_DIR

   def my_analysis_node(state):
       data = read_production_csv(DATA_DIR / "sample_production.csv")
       result = MyAnalyzer.analyze(data)
       return {
           **state,
           "response": f"My Analysis:\n{result.score}",
           "metadata": {**state.get("metadata", {}), **result.to_dict()},
       }
   ```

3. **Register the intent** in `src/graph/nodes/analyze.py`:

   ```python
   from . import my_analysis

   ANALYSIS_HANDLERS = {
       "oee": oee_analysis.oee_analysis_node,
       "bottleneck": bottleneck.bottleneck_node,
       "my_intent": my_analysis.my_analysis_node,   # ← add here
       ...
   }
   ```

4. **Add the intent to the classifier** in `src/graph/nodes/classify.py`:

   ```python
   VALID_INTENTS = ["oee", "bottleneck", "cost", "trend", "safety", "my_intent", "general"]
   ```

5. **Write tests** in `tests/test_my_analysis.py` — at minimum: engine unit tests, node runs without error, metadata keys present.

### Code style

- No comments unless the **why** is non-obvious
- No trailing summaries or explanatory docstrings
- Validation at system boundaries (CSV input, API body) only — trust internal code
- Run `pytest` before opening a PR — all tests must pass, 0 warnings

### Project conventions

- Persistent config → `src/config/loader.py` (`Config` dataclass)
- New API routes → new `APIRouter` in `src/api/`, included in `app.py`
- New CLI subcommand → new file in `src/cli/commands/`, registered in `src/cli/main.py`
- Database changes → new Alembic migration (`alembic revision --autogenerate -m "description"`)
