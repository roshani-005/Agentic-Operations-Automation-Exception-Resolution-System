from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.config import settings
from app.models import AgentPlan, AuditEvent, PlanStep, TaskState, VerificationResult
from app.tools import api_tool, extract_order_id, python_tool, sql_tool


class GraphState(TypedDict):
    state: TaskState


def audit(state: TaskState, stage: str, message: str, **data) -> None:
    state.audit_log.append(AuditEvent(stage=stage, message=message, data=data))


def planner_node(graph_state: GraphState) -> GraphState:
    state = graph_state["state"]
    order_id = extract_order_id(state.task)
    if not order_id:
        state.plan = AgentPlan(objective=state.task, steps=[])
        state.final_status = "human_review"
        state.final_answer = "The task does not contain a recognizable order identifier, so human clarification is required."
        audit(state, "planner", "Could not derive executable plan", reason="missing_order_id")
        return {"state": state}

    state.plan = AgentPlan(
        objective=f"Investigate operational exception for {order_id}",
        steps=[
            PlanStep(name="fetch_order", tool="sql", input={"order_id": order_id}),
            PlanStep(name="check_payment", tool="api", input={"order_id": order_id}),
            PlanStep(name="validate_case", tool="python", input={}),
        ],
    )
    audit(state, "planner", "Created execution plan", steps=[step.model_dump() for step in state.plan.steps])
    return {"state": state}


def router_node(graph_state: GraphState) -> GraphState:
    state = graph_state["state"]
    if state.final_status != "running" or not state.plan:
        return {"state": state}
    audit(state, "router", "Routing workflow to tool execution", current_step=state.current_step)
    return {"state": state}


async def tools_node(graph_state: GraphState) -> GraphState:
    state = graph_state["state"]
    if state.final_status != "running" or not state.plan:
        return {"state": state}

    state.tool_results = []
    order_result = sql_tool(state.plan.steps[0].input)
    state.tool_results.append(order_result)
    audit(state, "tool.sql", "Executed SQL lookup", success=order_result.success, result=order_result.data, error=order_result.error)

    api_result = await api_tool(state.plan.steps[1].input)
    state.tool_results.append(api_result)
    audit(state, "tool.api", "Executed payment API lookup", success=api_result.success, result=api_result.data, error=api_result.error)

    python_payload = {
        "order": order_result.data if order_result.success else {},
        "payment": api_result.data if api_result.success else {},
    }
    python_result = python_tool(python_payload)
    state.tool_results.append(python_result)
    audit(state, "tool.python", "Executed deterministic validation", success=python_result.success, result=python_result.data, error=python_result.error)
    return {"state": state}


def verify_node(graph_state: GraphState) -> GraphState:
    state = graph_state["state"]
    failed = [result for result in state.tool_results if not result.success]
    python_result = next((r for r in state.tool_results if r.tool == "python" and r.success), None)

    if failed:
        state.verification = VerificationResult(valid=False, reason="One or more required tools failed.")
    elif not python_result or not python_result.data.get("checks_passed"):
        state.verification = VerificationResult(valid=False, reason="The evidence is insufficient to verify the exception.")
    else:
        needs_human = bool(python_result.data.get("manual_review"))
        state.verification = VerificationResult(
            valid=True,
            reason="Required evidence was retrieved and deterministic checks completed.",
            needs_human_review=needs_human,
        )

    audit(state, "verification", "Verified execution results", verification=state.verification.model_dump())
    return {"state": state}


def correction_node(graph_state: GraphState) -> GraphState:
    state = graph_state["state"]
    state.retry_count += 1
    audit(state, "correction", "Preparing corrected retry", retry_count=state.retry_count)
    return {"state": state}


def finalize_node(graph_state: GraphState) -> GraphState:
    state = graph_state["state"]
    python_result = next((r for r in state.tool_results if r.tool == "python" and r.success), None)
    if state.verification and state.verification.needs_human_review:
        state.final_status = "human_review"
        state.final_answer = "The exception was investigated successfully, but business rules require human review."
    else:
        state.final_status = "completed"
        reasons = python_result.data.get("reasons", []) if python_result else []
        state.final_answer = f"Investigation completed. Verified reasons: {', '.join(reasons) if reasons else 'none'}."
    audit(state, "finalize", "Workflow reached terminal state", status=state.final_status)
    return {"state": state}


def escalate_node(graph_state: GraphState) -> GraphState:
    state = graph_state["state"]
    state.final_status = "human_review"
    state.final_answer = "Automated verification could not resolve the task within the retry limit. Human review is required."
    audit(state, "escalation", "Escalated task after retries", retry_count=state.retry_count)
    return {"state": state}


def after_planner(graph_state: GraphState) -> str:
    return "router" if graph_state["state"].final_status == "running" else "end"


def after_verify(graph_state: GraphState) -> str:
    state = graph_state["state"]
    if state.verification and state.verification.valid:
        return "finalize"
    if state.retry_count < settings.max_retries:
        return "correction"
    return "escalate"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("planner", planner_node)
    graph.add_node("router", router_node)
    graph.add_node("tools", tools_node)
    graph.add_node("verify", verify_node)
    graph.add_node("correction", correction_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("escalate", escalate_node)

    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", after_planner, {"router": "router", "end": END})
    graph.add_edge("router", "tools")
    graph.add_edge("tools", "verify")
    graph.add_conditional_edges("verify", after_verify, {"finalize": "finalize", "correction": "correction", "escalate": "escalate"})
    graph.add_edge("correction", "tools")
    graph.add_edge("finalize", END)
    graph.add_edge("escalate", END)
    return graph.compile()


workflow = build_graph()


async def run_workflow(task: str) -> TaskState:
    initial = TaskState(task=task)
    audit(initial, "received", "Task accepted for agentic execution")
    result = await workflow.ainvoke({"state": initial})
    return result["state"]
