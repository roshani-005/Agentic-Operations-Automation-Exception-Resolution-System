from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import settings
from app.database import Order, SessionLocal
from app.models import ToolResult


def sql_tool(payload: dict[str, Any]) -> ToolResult:
    order_id = payload.get("order_id")
    if not order_id:
        return ToolResult(tool="sql", success=False, error="order_id is required")

    with SessionLocal() as db:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return ToolResult(tool="sql", success=False, error=f"Order {order_id} not found")
        return ToolResult(
            tool="sql",
            success=True,
            data={
                "order_id": order.order_id,
                "customer_id": order.customer_id,
                "amount": order.amount,
                "status": order.status,
                "failure_reason": order.failure_reason,
            },
        )


async def api_tool(payload: dict[str, Any]) -> ToolResult:
    order_id = payload.get("order_id")
    if not order_id:
        return ToolResult(tool="api", success=False, error="order_id is required")

    # Deterministic local fallback makes the project runnable without a paid external service.
    if settings.payment_api_base_url == "https://example.com":
        status = "declined" if order_id.endswith("2") else "unknown"
        return ToolResult(tool="api", success=True, data={"order_id": order_id, "payment_status": status, "source": "demo-adapter"})

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(f"{settings.payment_api_base_url.rstrip('/')}/payments/{order_id}")
            response.raise_for_status()
            return ToolResult(tool="api", success=True, data=response.json())
    except Exception as exc:
        return ToolResult(tool="api", success=False, error=str(exc))


def python_tool(payload: dict[str, Any]) -> ToolResult:
    order = payload.get("order", {})
    payment = payload.get("payment", {})
    if not order:
        return ToolResult(tool="python", success=False, error="order data is required")

    reasons: list[str] = []
    if order.get("status") == "failed":
        reasons.append(order.get("failure_reason") or "order_failed")
    if payment.get("payment_status") == "declined":
        reasons.append("payment_declined_confirmed")

    manual_review = order.get("amount", 0) >= 10000 or order.get("failure_reason") == "inventory_mismatch"
    return ToolResult(
        tool="python",
        success=True,
        data={"manual_review": manual_review, "reasons": sorted(set(reasons)), "checks_passed": bool(reasons)},
    )


def extract_order_id(task: str) -> str | None:
    match = re.search(r"ORD-\d+", task.upper())
    return match.group(0) if match else None
