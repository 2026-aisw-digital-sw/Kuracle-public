from __future__ import annotations

from hobit_ax_agentos.agentos.runner import ServiceRunner
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import IncomingMessage


def test_dry_run_graph_excludes_action_agent_when_disabled() -> None:
    graph = ServiceRunner(settings=AppSettings(enable_action_agent=False)).dry_run_graph(
        IncomingMessage(
            channel="api",
            user_id="user_1",
            text="When is double major application?",
            session_id="session_1",
        )
    )

    node_by_id = {node["node_id"]: node for node in graph["nodes"]}
    assert set(node_by_id) == {
        "knowledge_query",
        "escalation_prepare",
        "final_response",
    }
    assert node_by_id["knowledge_query"]["params"]["output_schema"]["required"]
    assert any(
        edge["condition_expr"] == "requires_human_review == true"
        for edge in graph["edges"]
    )
    assert not any(edge["to_node_id"] == "action_prepare" for edge in graph["edges"])


def test_dry_run_graph_can_enable_action_agent_explicitly() -> None:
    graph = ServiceRunner(settings=AppSettings(enable_action_agent=True)).dry_run_graph(
        IncomingMessage(
            channel="api",
            user_id="user_1",
            text="When is double major application?",
            session_id="session_1",
        )
    )

    node_by_id = {node["node_id"]: node for node in graph["nodes"]}
    assert "action_prepare" in node_by_id
    assert any(
        edge["condition_expr"] == "requires_action == true"
        for edge in graph["edges"]
    )
