from __future__ import annotations

from typing import Any


class KnowledgeAgentTemplate:
    agent_id = "agent_hobit_knowledge"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = payload.get("message", {})
        query = str(message.get("text") or payload.get("query") or "")
        return {
            "answer": f"TODO: answer regulation question: {query}",
            "confidence": 0.0,
            "requires_action": False,
            "requires_human_review": True,
            "risk_class": "LOW",
            "cited_rule_ids": [],
            "cited_articles": [],
            "cited_content_sources": [],
            "workflow_status": "TEMPLATE",
            "intent_mode": None,
            "request_type": None,
            "issue_types": [],
            "coverage_report": {},
            "profile_gaps": [],
            "regulation_gaps": [],
            "unresolved_points": ["template_not_implemented"],
            "regulation_rag_trace_id": None,
            "state": {},
        }
