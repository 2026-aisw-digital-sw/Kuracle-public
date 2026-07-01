from __future__ import annotations

from typing import Any

from hobit_ax_agentos.adapters import RegulationRagAdapter
from hobit_ax_agentos.config import AppSettings


class KnowledgeAgent:
    agent_id = "agent_hobit_knowledge"

    def __init__(
        self,
        adapter: RegulationRagAdapter | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        self.adapter = adapter or RegulationRagAdapter(settings=settings)

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = payload.get("message", {})
        query = str(message.get("text") or payload.get("query") or "")
        profile = (message.get("metadata") or {}).get("profile")
        session_id = message.get("session_id")
        state = self.adapter.run_supervisor(query, profile=profile, session_id=session_id)
        answer = state.get("grounded_answer") or {}
        cited_rule_ids = answer.get("cited_rule_ids") or []
        unresolved = answer.get("unresolved_points") or []
        workflow_status = str(state.get("workflow_status") or "UNKNOWN")
        adapter_error = state.get("adapter_error")
        confidence = self._confidence(state, unresolved, adapter_error)
        parsed_intent = state.get("parsed_intent") or {}
        issue_graph = state.get("issue_graph") or []

        return {
            "answer": str(answer.get("summary") or ""),
            "confidence": confidence,
            "requires_action": self._requires_action(state),
            "requires_human_review": bool(
                adapter_error
                or workflow_status.upper() == "ESCALATED"
                or confidence < 0.7
                or answer.get("review_gate_triggered")
            ),
            "risk_class": "HIGH" if workflow_status.upper() == "ESCALATED" else "LOW",
            "cited_rule_ids": [str(rule_id) for rule_id in cited_rule_ids],
            "cited_articles": state.get("cited_articles") or [],
            "cited_content_sources": answer.get("cited_content_sources") or [],
            "workflow_status": workflow_status,
            "intent_mode": parsed_intent.get("intent_mode") or parsed_intent.get("mode"),
            "request_type": parsed_intent.get("request_type"),
            "issue_types": self._issue_types(issue_graph, parsed_intent),
            "coverage_report": state.get("coverage_report") or {},
            "profile_gaps": answer.get("profile_gaps") or state.get("missing_profile") or [],
            "regulation_gaps": answer.get("regulation_gaps") or [],
            "unresolved_points": unresolved,
            "regulation_rag_trace_id": state.get("regulation_rag_trace_id"),
            "state": state,
        }

    def _confidence(
        self,
        state: dict[str, Any],
        unresolved: list[Any],
        adapter_error: dict[str, Any] | None,
    ) -> float:
        if adapter_error:
            return 0.0
        packets = state.get("evidence_packets") or []
        confidences = [
            float(packet.get("confidence"))
            for packet in packets
            if isinstance(packet, dict) and isinstance(packet.get("confidence"), (int, float))
        ]
        if confidences:
            return max(0.0, min(1.0, sum(confidences) / len(confidences)))
        return 0.62 if unresolved else 0.86

    def _requires_action(self, state: dict[str, Any]) -> bool:
        intent = state.get("parsed_intent") or {}
        intent_mode = str(intent.get("intent_mode") or intent.get("mode") or "").lower()
        if intent_mode in {"procedure", "application", "action", "form"}:
            return True
        query = str(state.get("raw_query") or "")
        action_keywords = [
            "apply",
            "submit",
            "issue",
            "draft",
            "reserve",
            "\uc2e0\uccad",
            "\uc81c\ucd9c",
            "\ubc1c\uae09",
            "\uc791\uc131",
            "\uc608\uc57d",
        ]
        return any(keyword in query.lower() for keyword in action_keywords)

    def _issue_types(
        self,
        issue_graph: list[Any],
        parsed_intent: dict[str, Any],
    ) -> list[str]:
        issues = [
            str(item.get("issue_type"))
            for item in issue_graph
            if isinstance(item, dict) and item.get("issue_type")
        ]
        if not issues and parsed_intent.get("request_type"):
            issues.append(str(parsed_intent["request_type"]))
        return issues

