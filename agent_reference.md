# Godínez IndustrialEngineer — Agent Reference

Reference for an LLM agent (e.g. an OpenClaw agent) that needs to call the
Godínez IndustrialEngineer API on behalf of a user. Godínez is a
manufacturing analysis service — it answers plain-English questions about
production data with OEE scores, bottleneck detection, cost analysis, and
trend forecasts.

**Base URL:** `http://<host>:8000` — replace `<host>` with wherever the
container is reachable from you (`localhost` if on the same machine,
otherwise the Tailscale IP or hostname of the machine running it).

---

## How it works (need-to-know)

- Every request that runs an analysis goes through `POST /api/query` with a
  single natural-language `query` string — there is no separate endpoint
  per analysis type. The service classifies intent itself.
- Pass the **same `session_id`** across a whole conversation. This matters
  for two things: (1) a session's query history is retrievable later via
  `GET /api/results/{session_id}`, and (2) the "load dataset" command
  (below) scopes which CSV file is used to that `session_id` — every later
  query with the same `session_id` automatically uses the loaded dataset.
- If you don't pass `session_id`, one is auto-generated per request and not
  returned to you for reuse unless you read it from the response — always
  generate and pass your own `session_id` (e.g. a UUID or a stable name for
  the conversation) so follow-up queries land in the same session.
- Responses can take **6–150 seconds** — classification runs against an LLM
  (DGX primary, Ollama fallback, or instant keyword fallback if both are
  unreachable) and `trend` queries additionally render matplotlib charts.
  Don't assume a fast response; don't retry on slowness alone.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/query` | Run any analysis query (OEE, bottleneck, cost, trend, dataset commands) |
| `GET` | `/api/results/{session_id}` | Retrieve all past queries/results for a session |
| `POST` | `/api/data` | Upload a production CSV dataset |
| `GET` | `/api/data/list` | List available datasets |
| `DELETE` | `/api/data/{filename}` | Delete a dataset |
| `GET` | `/health` | Health check |
| `GET` | `/api/persistence/status` | Check whether results are being saved to a DB |

### `POST /api/query`

**Request:**
```json
{
  "query": "What is our OEE this week?",
  "session_id": "my-conversation-id",
  "user_id": "optional-user-identifier"
}
```
`query`: 1–2000 characters, required. `session_id`/`user_id`: optional but
recommended (see above).

**Response `200`:**
```json
{
  "query": "What is our OEE this week?",
  "response": "**OEE Analysis Report**\n...(markdown text)...",
  "intent": "oee",
  "session_id": "my-conversation-id",
  "metadata": {"oee_score": 86.1, "oee_rating": "good", "data_points": 84},
  "execution_summary": {"total_latency_ms": 1240},
  "charts": null,
  "success": true
}
```
- `response` is markdown — safe to relay to a chat user directly.
- `charts` is `null` for every intent except `trend`, where it's a list of
  `{"type": "...", "filename": "...", "base64": "..."}` objects (PNG images).
- `metadata` fields vary by intent (see "Recommended Prompts" below for
  what each one returns).
- **`500`**: LLM/internal error, body is `{"detail": {"error": "..."}}`.
- **`422`**: `query` missing or over 2000 characters.

### `GET /api/results/{session_id}`

Returns every query run in that session, most recent first — use this to
recall earlier turns in a conversation rather than re-asking the user.

### `POST /api/data` — upload a dataset

Multipart form upload, field name `file`. Must be `.csv`, ≤ 50 MB, and
contain these columns exactly: `date, shift, machine_id, planned_minutes,
actual_run_minutes, downtime_minutes, ideal_cycle_time_seconds, total_count,
good_count, downtime_reason`. Response includes the saved (timestamped)
filename — use that exact name in a `Load dataset` command afterward, not
the original filename you uploaded.

### `GET /api/data/list`

Returns every CSV currently available (filename, row count, date range,
machine IDs) — check this before telling a user "no data exists."

### `GET /health` / `GET /api/persistence/status`

Use these to confirm the service is reachable and whether query history is
actually being saved before promising a user their session will be
retrievable later.

---

## Recommended Prompts (by function)

Send these as the `query` field in `POST /api/query`. Phrasing matters —
see the **router priority gotcha** at the bottom before mixing keywords
from two categories in one prompt.

### OEE Analysis
Returns overall equipment effectiveness score, availability/performance/
quality breakdown, and top downtime causes.
- `"What is our OEE this week?"`
- `"What is our overall equipment effectiveness?"`
- `"How is equipment availability looking?"`

`metadata` returned: `oee_score`, `oee_rating`, `data_points`, `date_range`.

### Bottleneck Detection
Returns the constraint station, balance delay %, and per-machine findings
(cycle time variance, downtime concentration, capacity utilization).
- `"Where is our bottleneck?"`
- `"Show me bottlenecks on Line 2"`
- `"What is our production constraint?"`

`metadata` returned: `total_findings`, `critical_findings`.

### Cost Analysis
Returns waste cost breakdown (scrap, downtime, quality loss), Pareto
ranking by $ impact, and ROI projections for improvement scenarios.
- `"What is our total waste cost?"`
- `"Show cost breakdown for scrap and downtime"`
- `"What's our ROI on reducing rework?"`

`metadata` returned: `total_waste_cost`.

### Trend Analysis
Returns direction/forecast for OEE and its components, anomaly detection,
and (uniquely) chart images in the response's `charts` field.
- `"Show me the OEE trend analysis"`
- `"What is the production forecast for next month?"`
- `"Are there any anomalies in the data?"`

**Avoid the word "OEE" in trend prompts** — see gotcha below. Use "trend",
"forecast", "projection", or "time series" instead.

`metadata` returned: `machines_analyzed`, `data_points`.

### Dataset Commands (deterministic — no LLM call, instant)

**List what's available:**
- `"List datasets"`
- `"What datasets are available?"`
- `"Show me the available datasets"`

**Switch the active dataset for this session** (must be an exact filename
already present — check via `GET /api/data/list` or `"List datasets"` first):
- `'Load dataset "synthetic_production.csv"'`
- `'Use dataset "production_20260801_143022.csv"'`
- `'Switch dataset to "sample_production.csv"'`

Every later query in the same `session_id` then reads that dataset
automatically — you don't need to repeat the filename.

---

## Gotcha: keyword priority in intent routing

The keyword-fallback router checks categories in this fixed order: `oee` →
`bottleneck` → `trend` → `cost` → `safety` → `time_study`. A prompt
containing words from two categories resolves to whichever comes first in
that list — e.g. *"Show me the OEE trend"* always resolves to `oee`, never
`trend`, regardless of what the primary LLM classifier would have picked.
When composing a prompt for a specific function, stick to that function's
keywords only.

## Error handling for the calling agent

- If `POST /api/query` returns `500`, don't retry immediately — it usually
  means the LLM backend is down; the service still degrades to keyword
  matching automatically on the *next* call, so a retry after a short pause
  is reasonable.
- If a `Load dataset` command's response starts with `⚠️ Dataset not
  found`, it lists what's actually available in the same response — parse
  that instead of asking the user to guess a filename.
- `charts` will be `null` for every intent except `trend` — don't expect
  images back from an OEE/bottleneck/cost query.
