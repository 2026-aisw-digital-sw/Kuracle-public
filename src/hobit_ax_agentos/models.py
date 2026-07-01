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
class ServiceResult:
    run_id: str
    trace_id: str | None
    final: JsonMap | None
    run_summary: JsonMap
    worker_results: list[JsonMap]
