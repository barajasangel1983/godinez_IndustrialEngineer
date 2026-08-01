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
# Expected: 335 passed in ~25s
# (2 tracing tests in test_observability.py require a real LANGSMITH_API_KEY
# and will fail without one — unrelated to the rest of the suite)
```

Run a specific test file:
```bash
python -m pytest tests/test_workflow.py -q        # 40 tests — graph + nodes
python -m pytest tests/test_api.py -q             # 12 tests — FastAPI endpoints
python -m pytest tests/test_phase4.py -q          # 25 tests — bottleneck + cost
python -m pytest tests/test_comprehensive.py -q   # 60 tests — edge cases + security
python -m pytest tests/test_load_dataset.py -q    # 40 tests — dataset load/list commands
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

> **Note:** the active dataset is tracked in-memory per process
> (`src/graph/session_datasets.py`), scoped to `session_id`. It resets on
> container/process restart and is not shared across multiple worker
> processes — matches the current single-worker deployment
> (`uvicorn ... --workers 1`).

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
