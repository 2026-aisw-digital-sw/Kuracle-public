from __future__ import annotations

from typing import Any

from hobit_ax_agentos.models import CoordinationPlan


class PlanExecutionError(RuntimeError):
    """Raised when the kernel leases work outside the coordinator plan."""


def validate_lease_against_plan(
    *,
    plan: CoordinationPlan,
    node_id: str,
    agent_id: str,
) -> None:
    node_agents = _node_agents(plan)
    expected_agent = node_agents.get(node_id)
    if expected_agent is None:
        raise PlanExecutionError(f"node {node_id} is not in coordination plan {plan.plan_id}")
    if expected_agent != agent_id:
        raise PlanExecutionError(
            f"node {node_id} expected {expected_agent}, got {agent_id}"
        )
    if agent_id in plan.skipped_agents:
        raise PlanExecutionError(
            f"agent {agent_id} is marked skipped in coordination plan {plan.plan_id}"
        )


def summarize_plan_execution(
    *,
    plan: CoordinationPlan,
    worker_results: list[dict[str, Any]],
) -> dict[str, Any]:
    node_agents = _node_agents(plan)
    planned_order = {node_id: index for index, node_id in enumerate(node_agents)}
    executed_nodes = [str(item.get("node_id")) for item in worker_results]
    executed_agents = [str(item.get("agent_id")) for item in worker_results]
    violations: list[str] = []

    last_index = -1
    for node_id, agent_id in zip(executed_nodes, executed_agents):
        expected_agent = node_agents.get(node_id)
        if expected_agent is None:
            violations.append(f"unexpected_node:{node_id}")
            continue
        if expected_agent != agent_id:
            violations.append(f"agent_mismatch:{node_id}:{expected_agent}!={agent_id}")
        if agent_id in plan.skipped_agents:
            violations.append(f"skipped_agent_executed:{agent_id}")
        current_index = planned_order[node_id]
        if current_index < last_index:
            violations.append(f"out_of_order:{node_id}")
        last_index = max(last_index, current_index)

    skipped_conditional_nodes = [
        node_id for node_id in node_agents if node_id not in set(executed_nodes)
    ]
    return {
        "valid": not violations,
        "plan_id": plan.plan_id,
        "planned_nodes": list(node_agents.keys()),
        "executed_nodes": executed_nodes,
        "executed_agents": executed_agents,
        "skipped_conditional_nodes": skipped_conditional_nodes,
        "violations": violations,
    }


def _node_agents(plan: CoordinationPlan) -> dict[str, str]:
    node_agents: dict[str, str] = {}
    for node in plan.graph_nodes:
        node_id = node.get("node_id")
        agent_id = node.get("assigned_agent_id")
        if node_id and agent_id:
            node_agents[str(node_id)] = str(agent_id)
    return node_agents
