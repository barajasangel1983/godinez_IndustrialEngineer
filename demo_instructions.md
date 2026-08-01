# Godínez IndustrialEngineer — Demo Instructions

> **Audience:** Personal reference  
> **LLM fallback chain:** Qwen3.6-35B-A3B via vLLM on the DGX Spark (primary) → Ollama `qwen3:8b` (local fallback) → keyword matching (final fallback). No OpenAI key required.  
> **DGX reachability:** the classify node hits `DGX_VLLM_URL` directly (default `http://100.74.225.3:8001/v1`) — on a VPS this only works if Tailscale is up and connected to the DGX Spark's tailnet.  
> **Sections with OS differences:** Linux and Windows (PowerShell) blocks shown separately  
> **Docker sections:** identical on both platforms

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.13+ | `python --version` / `python3 --version` |
| Docker | 24+ | Includes Compose v2 (`docker compose`) |
| Ollama | 0.3+ | Optional — local fallback only, not required if DGX is reachable |
| Tailscale | any | Required on the VPS if you want the container to reach the DGX Spark's `Qwen/Qwen3.6-35B-A3B` vLLM endpoint |
| Git | any | |

---

## 2. LLM Backend Setup

### 2a. DGX (primary, via Tailscale)

The classify node's first attempt is always the DGX vLLM endpoint (`DGX_VLLM_URL`,
default `http://100.74.225.3:8001/v1`, serving `Qwen/Qwen3.6-35B-A3B`).

Confirm the VPS can reach it before running anything:
```bash
tailscale status   # DGX Spark node should show as connected
curl -s -o /dev/null -w "%{http_code}" http://100.74.225.3:8001/v1/models
# Expected: 200
```

A Docker container reaches this fine over the default bridge network — no
`--network=host` needed, since outbound traffic is NATed through the host,
which routes `100.x` addresses via `tailscale0`.

### 2b. Ollama (local fallback)

Used automatically when DGX is unreachable. Pull the required model once:

```bash
ollama pull qwen3:8b
ollama list   # confirm it shows qwen3:8b
```

Verify Ollama is listening:
```bash
# Expected: HTTP/1.1 200 OK
curl -s -o /dev/null -w "%{http_code}" http://localhost:11434/api/tags
```

If neither DGX nor Ollama is reachable, classification falls through to
keyword matching — analysis still works, just with lower-confidence intent
detection.

### 2c. Adding / changing a model

Unlike datasets (section 6a), there's no runtime `load model` prompt command
— the classify node (`src/graph/nodes/classify.py`) is the only place an LLM
is used anywhere in this codebase, and both models are hardcoded there.
Changing one is a source edit + rebuild, not an API call.

**To change the Ollama fallback model:**

1. Pull the new model:
   ```bash
   ollama pull <model-name>       # e.g. ollama pull llama3.2
   ollama list                    # confirm it shows up
   ```
2. Edit `src/graph/nodes/classify.py` — `_get_llm_ollama()` (around line 62):
   change `model="qwen3:8b"` to `model="<model-name>"`.
3. Rebuild and restart (local: just re-run `python main.py server`; Docker:
   `docker build -t godinez:latest . && docker stop godinez-demo && docker rm godinez-demo && docker run -d --name godinez-demo -p 8000:8000 --env-file .env godinez:latest`).

**To point at a different DGX / vLLM-served model:**

1. Set `DGX_VLLM_URL` in `.env` to the new endpoint (if it's a different
   host/port than the current one).
2. Edit `_get_llm_primary()` (around line 50) — change
   `model="Qwen/Qwen3.6-35B-A3B"` to whatever model ID that vLLM instance
   serves (check with `curl <DGX_VLLM_URL>/models`).
3. Rebuild and restart as above.

**Note:** `LLM_MODEL` / `LLM_TEMPERATURE` in `.env` and
`config --show` are defined in `src/config/` but are currently **not**
wired into `classify.py` — changing them has no effect on which model
actually runs. Editing the two `_get_llm_*()` functions directly is the
only thing that works today.

---

## 3. Local Setup

### Clone

```bash
git clone <repo-url> godinez_IndustrialEngineer
cd godinez_IndustrialEngineer
```

### Create virtual environment

**Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> If PowerShell blocks script execution: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure environment

**Linux**
```bash
cp .env.example .env
```

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
```

Edit `.env` — minimum required for local Ollama demo:

```env
# LLM — leave blank; classify node falls back to Ollama automatically
OPENAI_API_KEY=

# Persistence — SQLite (default), no extra setup needed
DATABASE_URL=sqlite:///data/godinez.db

# Everything else can stay as the .env.example defaults
```

### Verify install

```bash
python main.py --help
# Expected: usage: main.py [-h] {analyze,report,data,config,server} ...
```

---

## 4. Run Tests

```bash
python -m pytest --tb=short -q
# Expected: 343 passed in ~25s
# (2 tracing tests in test_observability.py require a real LANGSMITH_API_KEY
# and will fail without one — unrelated to the rest of the suite)
```

Run a specific test file:
```bash
python -m pytest tests/test_workflow.py -q        # 40 tests — graph + nodes
python -m pytest tests/test_api.py -q             # 12 tests — FastAPI endpoints
python -m pytest tests/test_phase4.py -q          # 25 tests — bottleneck + cost
python -m pytest tests/test_comprehensive.py -q   # 60 tests — edge cases + security
python -m pytest tests/test_load_dataset.py -q    # 43 tests — dataset load/list commands
python -m pytest tests/test_persistence.py -q     # 31 tests — DB models, config, repositories
```

---

## 5. Local Demo — CLI

Run each command in order. The workflow falls through DGX (unavailable) → Ollama → keyword fallback automatically.

```bash
# Show current configuration
python main.py config --show

# List available datasets
python main.py data --list

# Run an OEE analysis query (uses keyword fallback or Ollama)
python main.py analyze "What is our OEE this week?" --session demo-01

# Run a bottleneck query
python main.py analyze "Show me bottlenecks on Line 2" --session demo-01

# Run a cost analysis query
python main.py analyze "What is our total waste cost?" --session demo-01

# See what datasets are available (see section 6a)
python main.py analyze "List datasets" --session demo-01

# Switch the dataset used for the rest of this session
python main.py analyze 'Load dataset "synthetic_production.csv"' --session demo-01

# This query now reads synthetic_production.csv, not the default sample_production.csv
python main.py analyze "What is our OEE this week?" --session demo-01

# Generate a session report
python main.py report --session demo-01

# Start the API server (keep this terminal open for section 6)
python main.py server
```

---

## 6. Local Demo — API

Start the server first (`python main.py server`), then run these in a second terminal.

### Health check
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
# Expected: 200
```

### Persistence status
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/persistence/status
# Expected: 200
```

### Run a query

**Linux**
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our OEE this week?", "user_id": "demo-01"}'
# Expected: 200
```

**Windows (PowerShell)**
```powershell
curl.exe -s -o NUL -w "%{http_code}" `
  -X POST http://localhost:8000/api/query `
  -H "Content-Type: application/json" `
  -d '{\"query\": \"What is our OEE this week?\", \"user_id\": \"demo-01\"}'
# Expected: 200
```

### Dataset upload / list / switch

Covered in full in **section 6a** (upload, list via REST or prompt, switch the
active dataset per session). Quick smoke test:

**Linux**
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/data \
  -F "file=@data/sample_production.csv"
# Expected: 200
```

**Windows (PowerShell)**
```powershell
curl.exe -s -o NUL -w "%{http_code}" `
  -X POST http://localhost:8000/api/data `
  -F "file=@data/sample_production.csv"
# Expected: 200
```

### Retrieve session results
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/results/demo-01
# Expected: 200
```

### Delete a dataset
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE http://localhost:8000/api/data/sample_production.csv
# Expected: 200
```

---

## 6a. Dataset Management — Upload, List & Switch

Every analysis query (`oee`, `bottleneck`, `cost`, `trend`) reads a CSV dataset.
Without any dataset selection, every session defaults to
`data/sample_production.csv`.

### Upload a dataset

```bash
curl -s -X POST http://localhost:8000/api/data \
  -F "file=@/path/to/your_dataset.csv" | python3 -m json.tool
```

- Filename must end in `.csv`, ≤ 50 MB, and contain the required production
  columns (`date, shift, machine_id, planned_minutes, actual_run_minutes,
  downtime_minutes, ideal_cycle_time_seconds, total_count, good_count,
  downtime_reason`).
- Saved with a timestamped filename to avoid collisions
  (e.g. `your_dataset_20260801_030512.csv`) — the response's `filename`
  field is the exact name to use when loading it.

### Switch the active dataset for a session

Send a `Load dataset "<filename>"` command as a normal query, with a
`session_id`. This is matched deterministically (no LLM call) — recognized
phrasings are `load dataset X.csv`, `use dataset X.csv`, and
`switch dataset to X.csv` / `switch to dataset X.csv`.

```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Load dataset \"synthetic_production.csv\"", "session_id": "demo-01"}'
```

Response confirms row count, date range, and machine IDs. If the filename
doesn't exist (in `data/`, including uploads), the response lists what's
actually available instead:

```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Load dataset \"missing.csv\"", "session_id": "demo-01"}'
# Response: "⚠️ Dataset not found: missing.csv" + list of available datasets
```

Every subsequent query with the same `session_id` automatically uses the
loaded dataset — no need to repeat the filename:

```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the OEE trend?", "session_id": "demo-01"}'
# Reads synthetic_production.csv, not the default sample_production.csv
```

### List available datasets

Two equivalent ways to see what's in `data/`:

**Via REST** (raw JSON: filename, size, columns, date range, machine IDs):
```bash
curl -s http://localhost:8000/api/data/list | python3 -m json.tool
```

**Via prompt** (same deterministic matching as `Load dataset`, no LLM call).
Recognized phrasings: `list datasets`, `show datasets`,
`show me the available datasets`, `what datasets are available`,
`available datasets`.

```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "List datasets", "session_id": "demo-01"}'
```

The prompt version formats the same info as a readable summary and marks
whichever dataset is active for that `session_id`:

```
📁 Available datasets (2):
  - sample_production.csv — 66 rows, 2024-01-01 to 2024-01-30
  - synthetic_production.csv (active) — 728 rows, 2024-01-01 to 2024-06-30
```

### Delete a dataset

REST-only — no prompt command for this. See section 6 (`DELETE /api/data/{filename}`).

> **Note:** the active dataset (`src/graph/session_datasets.py`, scoped to
> `session_id`) is backed by the `sessions.active_dataset` DB column
> whenever persistence is enabled (`DATABASE_URL` set to a real database),
> so it's shared correctly across multiple uvicorn workers — `scripts/start.sh`
> runs 2+ workers by default the moment `DATABASE_URL` isn't `off`/SQLite,
> which an in-memory-only store would not survive. When persistence is off
> (local dev, or the single-container demo's `DATABASE_URL=off`), it falls
> back to an in-memory dict — correct there too, since that mode always
> stays single-worker — but is lost on restart in that case.

---

## 6b. Chart & Graph Testing

Test each chart type one at a time. Load the larger dataset first —
`synthetic_production.csv` has 728 rows across 6 months and 4 machines,
enough to clear every chart's data threshold (the default
`sample_production.csv` is too small for the control chart, see below):

```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Load dataset \"synthetic_production.csv\"", "session_id": "chart-test"}'
```

### Pull a chart file directly from the container

Every chart is rendered with `tempfile.gettempdir()` (`/tmp` inside the
container) as its save path, regardless of which intent triggered it. You
can always pull the latest-generated file out with `docker cp`, whether or
not that chart type is returned by the API:

```bash
# See what's currently in /tmp
docker exec godinez-demo sh -c 'ls -la /tmp/*.png'

# Copy one out to your current directory
docker cp godinez-demo:/tmp/oee_trend_chart.png ./oee_trend_chart.png
docker cp godinez-demo:/tmp/control_chart.png ./control_chart.png
docker cp godinez-demo:/tmp/pareto_chart.png ./pareto_chart.png
```

> **Caveat:** filenames aren't intent-specific — `oee_trend_chart.png` is
> written by both the `oee` intent and the `trend` intent (the `oee`
> version wraps the same function with `show_forecast=False`). Running one
> right after the other overwrites the same file, so `docker cp` always
> gets you the *most recently generated* chart of that type, not
> necessarily the one from the query you just ran. If that matters, `docker
> exec ... ls -la /tmp/*.png` first to check the modified time, or use the
> base64-in-response method below for the `trend` intent instead.

### Trend intent — 3 charts, returned in the API response

`trend` is the only intent whose charts actually come back in the JSON
response, base64-encoded in the `charts` field.

> **Gotcha:** `router_node` (`src/graph/nodes/router.py`) does a simple
> first-match keyword scan over the query, checked in this order: `oee`,
> `bottleneck`, `trend`, `cost`, `safety`, `time_study`. A prompt containing
> both "oee" and "trend" (e.g. *"Show me the OEE trend"*) matches `oee`
> first and never reaches the `trend` branch — this **overrides** whatever
> the real LLM classifier decided. Avoid the word "OEE" in trend prompts;
> use "trend", "forecast", "projection", or "time series" instead.

**1. OEE trend chart** (always generated if any data matches):
```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me the OEE trend analysis", "session_id": "chart-test"}' \
  | python3 -c 'import json,sys,base64; d=json.load(sys.stdin); [open(c["filename"],"wb").write(base64.b64decode(c["base64"])) for c in d["charts"]]; print([c["type"] for c in d["charts"]])'
# Expected: ["oee_trend", "control", "pareto"]
```

**2. Control chart** (needs ≥10 distinct dates in range — the full
`synthetic_production.csv` range qualifies; same command as above).

**3. Pareto chart** (needs ≥2 distinct downtime reasons — same command
as above).

The command above writes `oee_trend.png`, `control_chart.png`, and
`pareto_chart.png` to your current directory so you can open them directly.

### OEE intent — 2 charts, generated but NOT returned by the API

`oee_analysis_node` also builds an OEE trend chart and a downtime pie
chart (via a separate, older chart module), but `QueryResponse` has no
`attachments` field — they're rendered to a temp path inside the
container and then dropped, never reaching the JSON response. Use the
`docker cp` method above to pull them out and confirm:

```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our OEE?", "session_id": "chart-test"}' > /dev/null

docker cp godinez-demo:/tmp/oee_trend_chart.png ./oee_chart_from_oee_intent.png
```

### Bottleneck / cost intents — no charts

```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me bottlenecks", "session_id": "chart-test"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["charts"])'
# Expected: null — text-only response, no chart generation for this intent
```

---

## 7. Build & Run — Single Container (No DB)

No Compose, no Postgres. Simplest container demo. `DATABASE_URL=off` in `.env`
skips persistence entirely — results aren't saved across restarts, but the
CLI/API analysis flow works. Sample CSVs (`sample_production.csv`,
`synthetic_production.csv`) are baked into the image at build time (see
`Dockerfile`), so no upload step or volume mount is needed for this demo.

### Build
```bash
docker build -t godinez:latest .
```

### Run
```bash
docker run -d \
  --name godinez-demo \
  -p 8000:8000 \
  --env-file .env \
  godinez:latest
```

> Uses `--env-file .env` so the container picks up `DATABASE_URL=off` (no DB required)
> and `DGX_VLLM_URL` (Qwen3.6-35B-A3B via vLLM on the DGX Spark, reached over Tailscale).
> On a VPS with Tailscale connected to the DGX, this works over the default Docker bridge
> network — no `--network=host` needed, since outbound container traffic is NATed through
> the host, which routes `100.x` addresses via `tailscale0`.
>
> If the DGX/Tailscale link is unreachable, the classify node falls back to local Ollama
> (`OLLAMA_BASE_URL`), then to **keyword matching** — analysis still works either way.

### Verify

```bash
docker ps
```
You should see:
```
CONTAINER ID   IMAGE              COMMAND                  CREATED              STATUS              PORTS                                       NAMES
ddd7684a944d   godinez:latest     "./scripts/start.sh"     About a minute ago   Up About a minute   0.0.0.0:8000->8000/tcp, :::8000->8000/tcp   godinez-demo
```

```bash
# Wait ~5 seconds for startup, then:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
# Expected: 200

curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me OEE", "user_id": "container-test"}'
# Expected: 200 with a full OEE report in "response"
#   (metadata.classify_method: "primary" if DGX answered, "ollama" or
#   "keyword_fallback" otherwise). First DGX call can take 30-150s —
#   the vLLM endpoint is slow to respond to a cold request.
```

### Container logs
```bash
docker logs godinez-demo --follow
```

### Stop and remove
```bash
docker stop godinez-demo && docker rm godinez-demo
```

---

## 8. Deploy Full Stack — Docker Compose (PostgreSQL)

### Set required env var

**Linux**
```bash
export OPENAI_API_KEY=""   # empty is fine — Ollama/keyword fallback handles it
```

**Windows (PowerShell)**
```powershell
$env:OPENAI_API_KEY=""
```

### Start all services
```bash
docker compose up --build -d
```

Watch startup sequence (DB ready → Alembic migration → uvicorn):
```bash
docker compose logs app --follow
# Expected sequence:
#   Waiting for database...
#   Database ready (attempt N)
#   Running Alembic migrations...
#   Migrations complete.
#   Starting uvicorn: 2 worker(s) on port 8000
```

### Verify

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
# Expected: 200

curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/persistence/status
# Expected: 200  (body will show "postgresql" as database_type)

curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our OEE?", "user_id": "compose-test"}'
# Expected: 200
```

### Optional: Redis cache profile
```bash
docker compose --profile cache up --build -d
docker compose ps   # redis service should show as running
```

---

## 9. Verify Persistence Survives Restart

This confirms the PostgreSQL volume is working correctly.

```bash
# 1. Run a query and note the user_id
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show bottlenecks", "user_id": "persist-check"}'
# Expected: 200

# 2. Restart the app container (not the DB)
docker compose restart app

# 3. Wait for it to come back up
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
# Expected: 200

# 4. Retrieve the same session — result must still be there
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/results/persist-check
# Expected: 200 with results (not empty)
```

---

## 10. Teardown

### Stop Compose stack (keep volumes)
```bash
docker compose down
```

### Stop Compose stack and delete all data volumes
```bash
docker compose down -v
```

### Remove built image
```bash
docker rmi godinez:latest
```

### Deactivate local venv

**Linux**
```bash
deactivate
```

**Windows (PowerShell)**
```powershell
deactivate
```

---

## Quick Reference

| Task | Command |
|---|---|
| Run all tests | `python -m pytest -q` |
| Start API server | `python main.py server` |
| Run a query (CLI) | `python main.py analyze "..."` |
| Upload a dataset | `curl -X POST /api/data -F "file=@x.csv"` |
| Switch active dataset (session) | `python main.py analyze 'Load dataset "x.csv"' --session S` |
| List available datasets (prompt) | `python main.py analyze "List datasets" --session S` |
| Build container | `docker build -t godinez:latest .` |
| Start full stack | `docker compose up --build -d` |
| View app logs | `docker compose logs app --follow` |
| Tear down + wipe | `docker compose down -v` |
| Check Ollama model | `ollama list` |
| Pull Ollama model | `ollama pull qwen3:8b` |
| Check Tailscale link to DGX | `tailscale status` |
| Check DGX vLLM endpoint | `curl -s -o /dev/null -w "%{http_code}" http://100.74.225.3:8001/v1/models` |
