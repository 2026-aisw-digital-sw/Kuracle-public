from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
EXPECTED_AGENT_FOLDERS = {
    "agent_hobit_channel_gateway",
    "hobit_coordinator",
    "agent_hobit_persona",
    "agent_hobit_trigger",
    "agent_hobit_knowledge",
    "agent_hobit_action",
    "agent_hobit_escalation",
    "agent_hobit_final",
}
REQUIRED_FILES = {
    "agent.toml",
    "README.md",
    "contract.md",
    "template.py",
    "tests/test_contract_template.py",
}


def test_agent_workspace_folders_are_complete() -> None:
    folders = {
        path.name
        for path in AGENTS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }
    assert EXPECTED_AGENT_FOLDERS <= folders
    for folder in EXPECTED_AGENT_FOLDERS:
        base = AGENTS_DIR / folder
        for required in REQUIRED_FILES:
            assert (base / required).exists(), f"{folder}/{required} is missing"


def test_agent_workspace_manifests_are_consistent() -> None:
    seen_ids: set[str] = set()
    seen_nodes: set[str] = set()
    for folder in EXPECTED_AGENT_FOLDERS:
        manifest = tomllib.loads((AGENTS_DIR / folder / "agent.toml").read_text(encoding="utf-8"))
        agent_id = manifest["agent"]["id"]
        node_id = manifest["agentos"]["node_id"]
        editable_scope = manifest["development"]["editable_scope"]

        assert agent_id not in seen_ids
        assert node_id not in seen_nodes
        assert folder in editable_scope[0]
        assert manifest["contract"]["input_contract"].startswith("contract.md")
        assert manifest["contract"]["output_contract"].startswith("contract.md")
        assert manifest["development"]["template_entrypoint"] == "template.py"
        assert manifest["development"]["test_template"] == "tests/test_contract_template.py"

        seen_ids.add(agent_id)
        seen_nodes.add(node_id)


def test_graph_agent_workspace_ids_match_runtime_capabilities() -> None:
    from hobit_ax_agentos.agentos.capabilities import agent_capabilities

    runtime_ids = {capability.agent_id for capability in agent_capabilities()}
    graph_workspace_ids = {
        tomllib.loads((AGENTS_DIR / folder / "agent.toml").read_text(encoding="utf-8"))[
            "agent"
        ]["id"]
        for folder in {
            "agent_hobit_knowledge",
            "agent_hobit_action",
            "agent_hobit_escalation",
            "agent_hobit_final",
        }
    }
    assert graph_workspace_ids == runtime_ids
