from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.schemas import (
    ACTION_OUTPUT_SCHEMA,
    ESCALATION_OUTPUT_SCHEMA,
    FINAL_OUTPUT_SCHEMA,
    KNOWLEDGE_OUTPUT_SCHEMA,
)


@dataclass(frozen=True, slots=True)
class AgentCapability:
    agent_id: str
    capability_id: str
    name: str
    role: str
    node_id: str
    enabled: bool
    executor_kind: str = "thread"
    category: str = "RUNTIME"
    trust_tier: str = "BUILTIN"
    output_schema: dict[str, Any] | None = None
    disabled_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "capability_id": self.capability_id,
            "name": self.name,
            "role": self.role,
            "node_id": self.node_id,
            "enabled": self.enabled,
            "executor_kind": self.executor_kind,
            "category": self.category,
            "trust_tier": self.trust_tier,
            "output_schema": self.output_schema or {},
            "disabled_reason": self.disabled_reason,
        }


def capability_id_for_agent(agent_id: str) -> str:
    return f"cap.{agent_id}"


def agent_capabilities(settings: AppSettings | None = None) -> list[AgentCapability]:
    settings = settings or AppSettings()
    action_enabled = settings.enable_action_agent
    return [
        AgentCapability(
            agent_id="agent_hobit_knowledge",
            capability_id=capability_id_for_agent("agent_hobit_knowledge"),
            name="agent_hobit_knowledge.run",
            role="knowledge",
            node_id="knowledge_query",
            enabled=True,
            output_schema=KNOWLEDGE_OUTPUT_SCHEMA,
        ),
        AgentCapability(
            agent_id="agent_hobit_action",
            capability_id=capability_id_for_agent("agent_hobit_action"),
            name="agent_hobit_action.run",
            role="action",
            node_id="action_prepare",
            enabled=action_enabled,
            output_schema=ACTION_OUTPUT_SCHEMA,
            disabled_reason=(
                None if action_enabled else "deferred_until_contract_studio_bridge"
            ),
        ),
        AgentCapability(
            agent_id="agent_hobit_escalation",
            capability_id=capability_id_for_agent("agent_hobit_escalation"),
            name="agent_hobit_escalation.run",
            role="escalation",
            node_id="escalation_prepare",
            enabled=True,
            output_schema=ESCALATION_OUTPUT_SCHEMA,
        ),
        AgentCapability(
            agent_id="agent_hobit_final",
            capability_id=capability_id_for_agent("agent_hobit_final"),
            name="agent_hobit_final.run",
            role="final",
            node_id="final_response",
            enabled=True,
            output_schema=FINAL_OUTPUT_SCHEMA,
        ),
    ]


def enabled_agent_capabilities(settings: AppSettings | None = None) -> list[AgentCapability]:
    return [capability for capability in agent_capabilities(settings) if capability.enabled]
