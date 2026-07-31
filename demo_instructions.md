# Godínez IndustrialEngineer — Demo Instructions

> **Audience:** Personal reference  
> **LLM:** Ollama (`qwen3:8b`) — no OpenAI key required  
> **Sections with OS differences:** Linux and Windows (PowerShell) blocks shown separately  
> **Docker sections:** identical on both platforms

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.13+ | `python --version` / `python3 --version` |
| Docker | 24+ | Includes Compose v2 (`docker compose`) |
| Ollama | 0.3+ | Must be running before starting the app |
| Git | any | |

---

## 2. Ollama Setup

The classify node falls back to Ollama automatically when DGX is unreachable.  
Pull the required model once:

```bash
ollama pull qwen3:8b
ollama list   # confirm it shows qwen3:8b
```

Verify Ollama is listening:
```bash
# Expected: HTTP/1.1 200 OK
curl -s -o /dev/null -w "%{http_code}" http://localhost:11434/api/tags
```

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
# Expected: 297 passed in ~25s
```

Run a specific test file:
```bash
python -m pytest tests/test_workflow.py -q        # 40 tests — graph + nodes
python -m pytest tests/test_api.py -q             # 12 tests — FastAPI endpoints
python -m pytest tests/test_phase4.py -q          # 25 tests — bottleneck + cost
python -m pytest tests/test_comprehensive.py -q   # 60 tests — edge cases + security
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

### Upload a dataset

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

### List uploaded datasets
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/data/list
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

## 7. Build & Run — Single Container (SQLite)

No Compose, no Postgres. Simplest container demo.

### Build
```bash
docker build -t godinez:latest .
```

### Run
```bash
docker run -d \
  --name godinez-demo \
  -p 8000:8000 \
  -e DATABASE_URL=sqlite:///data/godinez.db \
  -e OPENAI_API_KEY="" \
  godinez:latest
```

> Ollama on the host is not reachable from inside the container by default.  
> The classify node will fall through to **keyword matching** — analysis still works.

### Verify

```bash
# Wait ~5 seconds for startup, then:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
# Expected: 200

curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me OEE", "user_id": "container-test"}'
# Expected: 200
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
| Build container | `docker build -t godinez:latest .` |
| Start full stack | `docker compose up --build -d` |
| View app logs | `docker compose logs app --follow` |
| Tear down + wipe | `docker compose down -v` |
| Check Ollama model | `ollama list` |
| Pull Ollama model | `ollama pull qwen3:8b` |
