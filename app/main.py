import json

from fastapi import FastAPI, HTTPException

from app.database import get_task, init_db, persist_task
from app.models import AuditEvent, TaskRequest, TaskResponse
from app.workflow import run_workflow


app = FastAPI(title="Agentic Operations Automation & Exception Resolution System", version="1.0.0")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tasks", response_model=TaskResponse)
async def create_task(payload: TaskRequest) -> TaskResponse:
    state = await run_workflow(payload.task)
    persist_task(state)
    return TaskResponse(
        task_id=state.task_id,
        status=state.final_status,
        answer=state.final_answer,
        retries=state.retry_count,
        audit_log=state.audit_log,
    )


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def read_task(task_id: str) -> TaskResponse:
    row = get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    events = [AuditEvent.model_validate(item) for item in json.loads(row.audit_json)]
    return TaskResponse(
        task_id=row.task_id,
        status=row.status,
        answer=row.answer,
        retries=row.retries,
        audit_log=events,
    )
