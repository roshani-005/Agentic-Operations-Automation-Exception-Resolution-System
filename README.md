# Agentic Operations Automation & Exception Resolution System

A production-style agentic workflow automation system built with FastAPI and LangGraph. It plans operational tasks, routes work to tools, verifies results, retries/corrects failures, escalates unresolved cases to humans, and records an auditable execution trail.

## Core flow

```text
User Task
   ↓
FastAPI
   ↓
LangGraph Orchestrator
   ↓
Planner
   ↓
Router
   ↓
SQL Tool / API Tool / Python Tool
   ↓
Verification
   ↓
Valid? ── yes ──> Complete
   │
   no
   ↓
Correction
   ↓
Retry
   ↓
Still failing? ── yes ──> Human Escalation
                              ↓
                           Audit Log
```

## Example use case

A user asks the system to investigate failed orders. The agentic workflow can:

1. plan the investigation,
2. query an operations database,
3. call an external payment-status API,
4. run deterministic Python validation,
5. verify the combined result,
6. retry/correct on failure,
7. escalate unresolved cases,
8. persist the decision and execution history.

## Stack

- Python
- FastAPI
- LangGraph
- OpenAI-compatible LLM API
- SQLAlchemy + SQLite (easy local run; can swap to PostgreSQL)
- Pydantic
- httpx
- Docker
- pytest
- GitHub Actions

## Endpoints

- `GET /health`
- `POST /tasks` — run an agentic task
- `GET /tasks/{task_id}` — inspect task status + audit trail

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Example request

```bash
curl -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"task":"Investigate failed order ORD-1002 and decide whether it needs manual review."}'
```

## Design choices

- Tool calls are explicit and typed.
- Deterministic validation is preferred for business rules.
- LLM output is schema-validated with Pydantic.
- Retries are capped to avoid infinite loops.
- Human escalation is a first-class terminal state.
- Every major step is written to the audit log.
- This project intentionally does **not** include RAG; it is focused on agentic operations automation.
