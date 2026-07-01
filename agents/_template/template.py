from __future__ import annotations

from typing import Any


class ExampleAgentTemplate:
    agent_id = "agent_example"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Implement the agent's AgentOS node behavior here."""
        raise NotImplementedError("Replace this template with agent-specific logic")
