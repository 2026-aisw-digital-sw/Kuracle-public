from __future__ import annotations

from uuid import uuid4

from hobit_ax_agentos.agentos.graph_builder import GraphBuilder, GraphBuildResult
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import CoordinationPlan, IncomingMessage, PersonaSnapshot
from hobit_ax_agentos.storage import CoordinationPlanStore


class CoordinatorAgent:
    agent_id = "hobit.coordinator"

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self.graph_builder = GraphBuilder(self.settings)
        self.plan_store = CoordinationPlanStore(self.settings.data_dir)

    def plan(self, message: IncomingMessage) -> GraphBuildResult:
        return self.graph_builder.build(message)

    def create_plan(
        self,
        message: IncomingMessage,
        persona: PersonaSnapshot | None = None,
    ) -> CoordinationPlan:
        classification = self.classify(message)
        graph_result = self.plan(message)
        graph_dict = graph_result.graph.to_dict()
        graph_nodes = graph_dict.get("nodes", [])
        selected_agents = [
            str(node["assigned_agent_id"])
            for node in graph_nodes
            if node.get("assigned_agent_id")
        ]
        skipped_agents = [] if self.settings.enable_action_agent else ["agent_hobit_action"]
        plan = CoordinationPlan(
            plan_id=f"plan_{uuid4().hex}",
            session_id=message.session_id,
            user_id=message.user_id,
            channel=message.channel,
            intent_family=classification["intent_family"],
            selected_agents=selected_agents,
            skipped_agents=skipped_agents,
            routing_reasons={
                # Heuristic, computed before knowledge_query runs (the graph hasn't
                # executed yet, so the real LLM-derived intent isn't known). ServiceRunner
                # patches in "actual_classification" once knowledge_query completes.
                "preliminary_classification": classification,
                "action_agent": (
                    "enabled_by_env"
                    if self.settings.enable_action_agent
                    else "deferred_until_contract_studio_bridge"
                ),
            },
            persona=persona.to_dict() if persona else {},
            graph_nodes=graph_nodes,
        )
        return self.plan_store.save(plan)

    def classify(self, message: IncomingMessage) -> dict:
        text = message.text.lower()
        if any(token in text for token in ["apply", "submit", "\uc2e0\uccad", "\uc81c\ucd9c"]):
            intent_family = "actionable_regulation"
        elif any(token in text for token in ["deadline", "\ub9c8\uac10", "\uae30\uac04"]):
            intent_family = "deadline_question"
        else:
            intent_family = "regulation_question"
        return {
            "intent_family": intent_family,
            "channel": message.channel,
            "user_id": message.user_id,
            "session_id": message.session_id,
        }
