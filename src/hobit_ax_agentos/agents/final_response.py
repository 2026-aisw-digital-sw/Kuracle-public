from __future__ import annotations

from typing import Any


class FinalResponseAgent:
    agent_id = "agent_hobit_final"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        knowledge = payload.get("knowledge") or {}
        action = payload.get("action") or {}
        escalation = payload.get("escalation") or {}
        response = knowledge.get("answer") or "No answer was generated."
        if escalation.get("requires_human_review"):
            response = (response or "").rstrip()
            if response:
                response = f"{response}\n\n담당자가 확인 후 안내해 드리겠습니다."
            else:
                response = "담당자가 확인 후 안내해 드리겠습니다."
        action_plan = action.get("action_plan")
        if action_plan and isinstance(action_plan, dict):
            guide = _compose_action_guide(action_plan)
            if guide:
                response = f"{response}\n\n{guide}".strip()
        return {
            "response": response,
            "delivery": {
                "channel": payload.get("channel", "api"),
                "action_plan": action_plan,
                "escalation": escalation,
            },
        }


# ── Form Guide Builder (Phase 1 — static template) ────────────────────────────

def _compose_action_guide(plan: dict[str, Any]) -> str:
    """Build a natural-language action guide from an ActionPlan dict.

    Produces a deterministic, template-based guide (Phase 1). LLM-based
    personalisation from evidence_packets is deferred to Phase 2.
    """
    form_name = str(plan.get("form_name") or "")
    steps: list[dict[str, Any]] = plan.get("steps") or []
    required_docs: list[str] = plan.get("required_docs") or []
    portal_url: str | None = plan.get("portal_url")
    deadline: str | None = plan.get("deadline")
    cautions: list[str] = plan.get("cautions") or []

    lines: list[str] = []

    header = f"[{form_name} 신청 안내]" if form_name else "[신청 안내]"
    lines.append(header)

    if deadline:
        lines.append(f"마감: {deadline}")

    if required_docs:
        lines.append(f"필요 서류: {', '.join(required_docs)}")

    if steps:
        lines.append("신청 절차:")
        for step in steps:
            order = step.get("order", "")
            name = step.get("name", "")
            desc = step.get("description", "")
            method = step.get("method", "")
            method_tag = f" [{method}]" if method and method != "portal" else ""
            lines.append(f"  {order}. {name}{method_tag}: {desc}")

    if portal_url:
        lines.append(f"포털 링크: {portal_url}")

    if cautions:
        lines.append("주의사항: " + " / ".join(cautions))

    return "\n".join(lines) if len(lines) > 1 else ""
