from __future__ import annotations

from hobit_ax_agentos.agentos.capabilities import agent_capabilities, enabled_agent_capabilities
from hobit_ax_agentos.config import AppSettings


def test_agent_capabilities_disable_action_agent_by_default() -> None:
    capabilities = agent_capabilities(AppSettings(enable_action_agent=False))
    by_agent = {capability.agent_id: capability for capability in capabilities}

    assert by_agent["agent_hobit_knowledge"].enabled is True
    assert by_agent["agent_hobit_escalation"].enabled is True
    assert by_agent["agent_hobit_final"].enabled is True
    assert by_agent["agent_hobit_action"].enabled is False
    assert by_agent["agent_hobit_action"].disabled_reason == (
        "deferred_until_contract_studio_bridge"
    )
    assert [
        capability.agent_id
        for capability in enabled_agent_capabilities(AppSettings(enable_action_agent=False))
    ] == [
        "agent_hobit_knowledge",
        "agent_hobit_escalation",
        "agent_hobit_final",
    ]


def test_agent_capabilities_can_enable_action_agent_explicitly() -> None:
    capabilities = enabled_agent_capabilities(AppSettings(enable_action_agent=True))

    assert [capability.agent_id for capability in capabilities] == [
        "agent_hobit_knowledge",
        "agent_hobit_action",
        "agent_hobit_escalation",
        "agent_hobit_final",
    ]
    assert capabilities[1].output_schema["required"] == [
        "action_plan",
        "requires_human_approval",
    ]
