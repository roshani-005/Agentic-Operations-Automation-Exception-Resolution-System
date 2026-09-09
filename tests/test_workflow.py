import pytest

from app.database import init_db
from app.workflow import run_workflow


@pytest.mark.asyncio
async def test_failed_payment_case_completes_without_human_review():
    init_db()
    state = await run_workflow("Investigate failed order ORD-1002 and decide whether it needs manual review.")
    assert state.final_status == "completed"
    assert any(event.stage == "verification" for event in state.audit_log)
    assert any(result.tool == "sql" for result in state.tool_results)


@pytest.mark.asyncio
async def test_inventory_mismatch_escalates_to_human_review():
    init_db()
    state = await run_workflow("Investigate failed order ORD-1003 and decide whether it needs manual review.")
    assert state.final_status == "human_review"
    assert state.verification is not None
    assert state.verification.needs_human_review is True


@pytest.mark.asyncio
async def test_missing_order_id_requires_clarification():
    state = await run_workflow("Investigate the failed order and resolve the exception.")
    assert state.final_status == "human_review"
