from __future__ import annotations

import json
import logging
from uuid import uuid4

from hobit_ax_agentos.agentos.graph_builder import GraphBuilder, GraphBuildResult
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import CoordinationPlan, IncomingMessage, PersonaSnapshot
from hobit_ax_agentos.storage import CoordinationPlanStore

logger = logging.getLogger(__name__)

# 7-class intent → 3-class intent_family (graph routing)
_INTENT_TO_FAMILY: dict[str, str] = {
    "regulation": "regulation_question",
    "action": "actionable_regulation",
    "general_info": "regulation_question",
    "profile_query": "regulation_question",
    "feedback": "regulation_question",
    "out_of_scope": "regulation_question",
    "chitchat": "regulation_question",
    "deadline_question": "deadline_question",  # keyword-fallback only
}

_CLASSIFY_SYSTEM = (
    "You are an intent classifier for hoBIT-AX, a Korean university academic regulation assistant.\n"
    "Classify the user message into exactly one intent class.\n\n"
    "Classes:\n"
    "- regulation: question about academic regulations, conditions, eligibility, deadlines\n"
    "- action: request to help with an application, procedure, or document "
    "(신청, 제출, 서류, 작성, 예약, 신청서, 어떻게 해)\n"
    "- general_info: general campus/schedule information not about specific regulations\n"
    "- profile_query: asking about their own academic records or current enrollment status\n"
    "- feedback: commenting on or rating a previous answer\n"
    "- out_of_scope: completely unrelated to academic affairs or university\n"
    "- chitchat: greeting, small talk, casual conversation\n\n"
    'Respond with JSON only (no extra text): {"intent_class": "<class>", "confidence": <0.0-1.0>}'
)


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
                # Full 7-class classification stored for observability and future routing.
                # ServiceRunner patches in "actual_classification" once knowledge_query completes.
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
        """Classify user intent — LLM (7-class) with keyword heuristic fallback."""
        base = {
            "channel": message.channel,
            "user_id": message.user_id,
            "session_id": message.session_id,
        }
        if self.settings.openai_api_key:
            llm_result = self._classify_with_llm(message.text)
            if llm_result:
                return {**base, **llm_result}
        return {**base, **self._classify_heuristic(message.text)}

    # ── LLM path ──────────────────────────────────────────────────────────────

    def _classify_with_llm(self, text: str) -> dict | None:
        try:
            import openai

            client = openai.OpenAI(api_key=self.settings.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _CLASSIFY_SYSTEM},
                    {"role": "user", "content": text},
                ],
                temperature=0,
                max_tokens=64,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            parsed = json.loads(raw)
            intent_class = str(parsed.get("intent_class") or "regulation")
            if intent_class not in _INTENT_TO_FAMILY:
                logger.warning(
                    "[CoordinatorAgent] LLM returned unknown intent_class=%s, defaulting to regulation",
                    intent_class,
                )
                intent_class = "regulation"
            return {
                "intent_class": intent_class,
                "intent_family": _INTENT_TO_FAMILY[intent_class],
                "confidence": float(parsed.get("confidence") or 0.9),
                "classifier": "llm",
            }
        except Exception as exc:
            logger.warning(
                "[CoordinatorAgent] LLM classify failed, falling back to heuristic: %s", exc
            )
            return None

    # ── Heuristic fallback ────────────────────────────────────────────────────

    def _classify_heuristic(self, text: str) -> dict:
        lowered = text.lower()
        if any(t in lowered for t in ["apply", "submit", "신청", "제출", "서류", "작성", "예약"]):
            intent_class, intent_family = "action", "actionable_regulation"
        elif any(t in lowered for t in ["deadline", "마감", "기간"]):
            intent_class, intent_family = "deadline_question", "deadline_question"
        else:
            intent_class, intent_family = "regulation", "regulation_question"
        return {
            "intent_class": intent_class,
            "intent_family": intent_family,
            "confidence": 0.6,
            "classifier": "heuristic",
        }
