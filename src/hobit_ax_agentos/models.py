from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


JsonMap = dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class IncomingMessage:
    channel: str
    user_id: str
    text: str
    session_id: str
    attachments: list[JsonMap] = field(default_factory=list)
    metadata: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class UserProfileRecord:
    """regulation_rag UserProfile.from_dict() 입력과 동일한 모양을 유지한다.

    profile_type은 regulation_rag domain.enums.UserType 값과 맞춘다
    ("student" | "staff" | "faculty" | "public"). profile은 해당
    StudentProfile/StaffProfile/FacultyProfile/PublicProfile.from_dict()가
    기대하는 필드 그대로 저장한다.
    """

    user_id: str
    profile_type: Literal["student", "staff", "faculty", "public"]
    profile: JsonMap = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class PersonaSnapshot:
    session_id: str
    user_id: str
    top_issue_types: list[str] = field(default_factory=list)
    predicted_questions: list[str] = field(default_factory=list)
    profile: JsonMap = field(default_factory=dict)
    source: str = "deterministic"
    prefetch_result: JsonMap = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class TriggerEvent:
    trigger_id: str
    event_type: str
    user_id: str
    session_id: str
    message: IncomingMessage
    metadata: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        data = asdict(self)
        data["message"] = self.message.to_dict()
        return data


@dataclass(slots=True)
class DeadlineWatch:
    watch_id: str
    user_id: str
    session_id: str
    issue_type: str
    deadline: str
    status: Literal["ACTIVE", "PAUSED", "COMPLETED"] = "ACTIVE"
    reminder_window_days: int = 7
    source: str = "manual"
    metadata: JsonMap = field(default_factory=dict)
    last_triggered_on: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class EscalationCase:
    escalation_id: str
    session_id: str
    user_id: str
    reason: str
    status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"] = "OPEN"
    review_package: JsonMap = field(default_factory=dict)
    trace_id: str | None = None
    run_id: str | None = None
    regulation_rag_trace_id: str | None = None
    resolution_signal: str | None = None
    resolution_comment: str | None = None
    assignee: str | None = None
    notes: list[JsonMap] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class ConversationTurn:
    turn_id: str
    session_id: str
    user_id: str
    channel: str
    text: str
    role: Literal["USER", "ASSISTANT", "SYSTEM"] = "USER"
    metadata: JsonMap = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class CoordinationPlan:
    plan_id: str
    session_id: str
    user_id: str
    channel: str
    intent_family: str
    selected_agents: list[str]
    skipped_agents: list[str] = field(default_factory=list)
    routing_reasons: JsonMap = field(default_factory=dict)
    persona: JsonMap = field(default_factory=dict)
    graph_nodes: list[JsonMap] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class AgentRunRecord:
    run_id: str
    session_id: str
    user_id: str
    channel: str
    state: str
    trace_id: str | None = None
    coordination_plan_id: str | None = None
    graph_id: str | None = None
    final: JsonMap | None = None
    run_summary: JsonMap = field(default_factory=dict)
    worker_results: list[JsonMap] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class AsyncJobRecord:
    job_id: str
    kind: str
    session_id: str
    user_id: str
    channel: str
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"] = "QUEUED"
    message: JsonMap = field(default_factory=dict)
    run_id: str | None = None
    trace_id: str | None = None
    result: JsonMap | None = None
    error_type: str | None = None
    error: str | None = None
    metadata: JsonMap = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class OutboundDelivery:
    delivery_id: str
    session_id: str
    user_id: str
    channel: str
    text: str
    status: Literal["PENDING", "SENT", "FAILED"] = "PENDING"
    payload: JsonMap = field(default_factory=dict)
    run_id: str | None = None
    trace_id: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    sent_at: str | None = None

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class AcademicEvent:
    """User-specific academic calendar item.

    Created when Action Agent produces an action plan with a deadline, or when
    TriggerAgent fires a deadline event. Gives agents a unified user timeline view.
    """

    event_id: str
    user_id: str
    session_id: str
    event_type: Literal["deadline", "registration", "notification", "action", "custom"]
    issue_type: str
    title: str
    due_date: str  # ISO date string (YYYY-MM-DD)
    status: Literal["ACTIVE", "COMPLETED", "DISMISSED"] = "ACTIVE"
    source: str = "system"
    run_id: str | None = None
    metadata: JsonMap = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class PendingAction:
    """An action plan produced by ActionAgent that has not yet been submitted.

    Created when ActionAgent generates a form draft / checklist. Marked SUBMITTED
    once the user completes the portal action, or CANCELLED if they abandon it.
    """

    action_id: str
    user_id: str
    session_id: str
    issue_type: str
    form_name: str
    status: Literal["PENDING", "SUBMITTED", "CANCELLED"] = "PENDING"
    action_plan: JsonMap = field(default_factory=dict)
    run_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class RegulationGap:
    """Recurring unresolved regulation query logged after Escalation resolution.

    Tracks questions that the system cannot answer confidently. Accumulates across
    sessions to surface which regulation areas need authoring attention.
    """

    gap_id: str
    issue_type: str
    query: str
    frequency: int = 1
    status: Literal["OPEN", "RESOLVED"] = "OPEN"
    user_id: str | None = None
    session_id: str | None = None
    escalation_id: str | None = None
    resolution: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class ProfileGateRecord:
    """Stores a deferred question while the system collects missing profile fields.

    When KnowledgeAgent returns non-empty profile_gaps, ServiceRunner creates one of
    these. On the next turn from the same user/session, ServiceRunner detects the
    active gate, injects the new message as profile info, and re-runs the original
    question. Expires after max_retries attempts.
    """

    gate_id: str
    session_id: str
    user_id: str
    original_text: str
    missing_fields: list[str]
    status: Literal["WAITING", "RESOLVED", "EXPIRED"] = "WAITING"
    retry_count: int = 0
    max_retries: int = 2
    run_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> JsonMap:
        return asdict(self)


@dataclass(slots=True)
class ServiceResult:
    run_id: str
    trace_id: str | None
    final: JsonMap | None
    run_summary: JsonMap
    worker_results: list[JsonMap]
