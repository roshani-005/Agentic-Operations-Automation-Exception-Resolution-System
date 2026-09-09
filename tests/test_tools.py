from app.database import init_db
from app.tools import python_tool, sql_tool


def setup_module():
    init_db()


def test_sql_tool_finds_seeded_failed_order():
    result = sql_tool({"order_id": "ORD-1002"})
    assert result.success is True
    assert result.data["status"] == "failed"
    assert result.data["failure_reason"] == "payment_declined"


def test_python_tool_routes_large_exception_to_manual_review():
    result = python_tool({
        "order": {"status": "failed", "amount": 15000, "failure_reason": "inventory_mismatch"},
        "payment": {"payment_status": "unknown"},
    })
    assert result.success is True
    assert result.data["manual_review"] is True
