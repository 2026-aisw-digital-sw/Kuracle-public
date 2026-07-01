from __future__ import annotations

import logging
from typing import Any

from hobit_ax_agentos.adapters import RegulationRagAdapter
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import IncomingMessage, PersonaSnapshot
from hobit_ax_agentos.storage import ConversationStore, ProfileStore

logger = logging.getLogger(__name__)


class PersonaPrefetchService:
    """LLM-backed persona enrichment for the on-demand "/persona/prefetch" path.

    This is distinct from agents.persona.PersonaWorker, which stays synchronous and
    LLM-free because it runs inside every ServiceRunner.run_message() call. This
    service is the session-event-triggered counterpart the architecture doc describes:
    it predicts likely follow-up questions for a session (one LLM call) and runs them
    through the shared Supervisor in the background to warm regulation_rag's
    QueryCache, using regulation_rag.workers.persona_worker as-is rather than
    reimplementing it.
    """

    def __init__(
        self,
        settings: AppSettings | None = None,
        adapter: RegulationRagAdapter | None = None,
        conversation_store: ConversationStore | None = None,
        profile_store: ProfileStore | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.adapter = adapter or RegulationRagAdapter(settings=self.settings)
        self.conversation_store = conversation_store or ConversationStore(self.settings.data_dir)
        self.profile_store = profile_store or ProfileStore(self.settings.data_dir)

    def prefetch(self, message: IncomingMessage) -> PersonaSnapshot:
        from hobit_ax_agentos.agents.persona import PersonaWorker

        history = [
            turn.to_dict()
            for turn in self.conversation_store.list_by_session(message.session_id)
        ]
        deterministic = PersonaWorker().build(message, history=history)

        stored_profile = self.profile_store.get(message.user_id)
        if stored_profile is None:
            logger.info(
                "[PersonaPrefetchService] no stored profile for user_id=%s, "
                "skipping LLM prediction",
                message.user_id,
            )
            return deterministic

        profile_dict = {
            "profile_type": stored_profile.profile_type,
            "profile": stored_profile.profile,
        }
        try:
            return self._llm_prefetch(message, profile_dict, deterministic)
        except Exception as exc:
            logger.warning(
                "[PersonaPrefetchService] LLM prefetch failed, falling back to "
                "deterministic snapshot: %s",
                exc,
            )
            return deterministic

    def _llm_prefetch(
        self,
        message: IncomingMessage,
        profile_dict: dict[str, Any],
        deterministic: PersonaSnapshot,
    ) -> PersonaSnapshot:
        user_profile = self.adapter.build_user_profile(profile_dict)
        if user_profile is None:
            return deterministic

        from regulation_rag.workers.persona_worker import (
            build_persona,
            predict_questions,
            prefetch_background,
        )

        trace_store = self.adapter.get_trace_store()
        persona_vector = build_persona(message.session_id, user_profile, trace_store)
        persona_vector.predicted_questions = predict_questions(persona_vector)

        supervisor = self.adapter.get_supervisor(profile_dict)
        prefetch_result = prefetch_background(persona_vector, supervisor)

        return PersonaSnapshot(
            session_id=message.session_id,
            user_id=message.user_id,
            top_issue_types=persona_vector.top_issue_types or deterministic.top_issue_types,
            predicted_questions=persona_vector.predicted_questions,
            profile=dict(profile_dict.get("profile") or {}),
            source="llm",
            prefetch_result={
                "triggered": prefetch_result.triggered,
                "succeeded": prefetch_result.succeeded,
                "failed": prefetch_result.failed,
                "questions": prefetch_result.questions,
            },
        )
