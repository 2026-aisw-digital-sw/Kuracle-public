from __future__ import annotations

from dataclasses import dataclass

from hobit_ax_agentos.config import AppSettings, bootstrap_local_dependencies
from hobit_ax_agentos.models import IncomingMessage
from hobit_ax_agentos.schemas import (
    ACTION_OUTPUT_SCHEMA,
    ESCALATION_OUTPUT_SCHEMA,
    FINAL_OUTPUT_SCHEMA,
    KNOWLEDGE_OUTPUT_SCHEMA,
)


@dataclass(slots=True)
class GraphBuildResult:
    graph: object
    nodes: dict[str, str]


class GraphBuilder:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        bootstrap_local_dependencies(self.settings)

    def build(self, message: IncomingMessage) -> GraphBuildResult:
        from agentos_sdk import ResourceBudget, TaskEdge, TaskGraphIR, TaskNode

        knowledge = TaskNode(
            node_id="knowledge_query",
            name="Knowledge Query",
            kind="TOOL",
            assigned_agent_id="agent_hobit_knowledge",
            params={
                "agent": "knowledge",
                "message": message.to_dict(),
                "executor_kind": "thread",
                "output_schema": KNOWLEDGE_OUTPUT_SCHEMA,
            },
        )
        escalation = TaskNode(
            node_id="escalation_prepare",
            name="Prepare Escalation",
            kind="TOOL",
            assigned_agent_id="agent_hobit_escalation",
            params={
                "agent": "escalation",
                "executor_kind": "thread",
                "output_schema": ESCALATION_OUTPUT_SCHEMA,
            },
        )
        final = TaskNode(
            node_id="final_response",
            name="Compose Final Response",
            kind="TOOL",
            assigned_agent_id="agent_hobit_final",
            params={
                "agent": "final",
                "executor_kind": "thread",
                "output_schema": FINAL_OUTPUT_SCHEMA,
            },
        )
        nodes = [knowledge, escalation, final]
        edges = [
            TaskEdge(
                from_node_id="knowledge_query",
                to_node_id="escalation_prepare",
                condition_expr="requires_human_review == true",
            ),
            TaskEdge("knowledge_query", "final_response"),
            TaskEdge("escalation_prepare", "final_response"),
        ]
        node_ids = {
            "knowledge": "knowledge_query",
            "escalation": "escalation_prepare",
            "final": "final_response",
        }
        if self.settings.enable_action_agent:
            action = TaskNode(
                node_id="action_prepare",
                name="Prepare Action Plan",
                kind="TOOL",
                assigned_agent_id="agent_hobit_action",
                params={
                    "agent": "action",
                    "executor_kind": "thread",
                    "output_schema": ACTION_OUTPUT_SCHEMA,
                },
            )
            nodes.append(action)
            edges.extend(
                [
                    TaskEdge(
                        from_node_id="knowledge_query",
                        to_node_id="action_prepare",
                        condition_expr="requires_action == true",
                    ),
                    TaskEdge("action_prepare", "final_response"),
                ]
            )
            node_ids["action"] = "action_prepare"

        graph = TaskGraphIR(
            intent_id=f"hobit:{message.session_id}",
            nodes=nodes,
            edges=edges,
            resource_budget=ResourceBudget(max_concurrent_leases=3),
        )
        return GraphBuildResult(
            graph=graph,
            nodes=node_ids,
        )

