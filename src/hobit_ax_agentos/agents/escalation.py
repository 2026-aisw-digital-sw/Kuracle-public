from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import EscalationCase
from hobit_ax_agentos.storage import EscalationStore

logger = logging.getLogger(__name__)


class EscalationAgent:
    agent_id = "agent_hobit_escalation"

    def __init__(
        self,
        settings: AppSettings | None = None,
        store: EscalationStore | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.store = store or EscalationStore(self.settings.data_dir)
        self._adapter = None

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        knowledge = payload.get("knowledge") or payload
        reason = "low_confidence"
        if knowledge.get("requires_human_review"):
            reason = "human_review_required"
        if knowledge.get("risk_class") == "HIGH":
            reason = "high_risk"

        review_package = {
            "answer": knowledge.get("answer"),
            "confidence": knowledge.get("confidence"),
            "cited_rule_ids": knowledge.get("cited_rule_ids") or [],
            "unresolved_points": knowledge.get("unresolved_points") or [],
            "workflow_status": knowledge.get("workflow_status"),
            "issue_types": knowledge.get("issue_types") or [],
            "regulation_gaps": knowledge.get("regulation_gaps") or [],
        }
        context = payload.get("context") or {}
        case = self.store.save(
            EscalationCase(
                escalation_id=f"esc_{uuid4().hex}",
                session_id=str(context.get("session_id") or self.settings.default_session_id),
                user_id=str(context.get("user_id") or self.settings.default_user_id),
                reason=reason,
                review_package=review_package,
                trace_id=context.get("trace_id"),
                run_id=context.get("run_id"),
                regulation_rag_trace_id=knowledge.get("regulation_rag_trace_id"),
            )
        )
        return {
            "requires_human_review": True,
            "reason": reason,
            "escalation_id": case.escalation_id,
            "review_package": review_package,
        }

    def resolve(
        self,
        escalation_id: str,
        signal: str = "neutral",
        comment: str | None = None,
    ) -> EscalationCase:
        """Resolve a case and, if it carries a regulation_rag trace, feed the human
        review outcome back into regulation_rag's self-strengthening feedback loop."""
        case = self.store.resolve(escalation_id, signal=signal, comment=comment)
        if case.regulation_rag_trace_id:
            self._record_feedback(case.regulation_rag_trace_id, signal, comment, case.session_id)
        return case

    def _record_feedback(
        self,
        trace_id: str,
        signal: str,
        comment: str | None,
        session_id: str | None,
    ) -> None:
        try:
            if self._adapter is None:
                from hobit_ax_agentos.adapters import RegulationRagAdapter

                self._adapter = RegulationRagAdapter(settings=self.settings)
            self._adapter.record_feedback(
                trace_id=trace_id, signal=signal, comment=comment, session_id=session_id
            )
        except Exception as exc:
            logger.warning("[EscalationAgent] failed to record regulation_rag feedback: %s", exc)
