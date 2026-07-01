from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import DeadlineWatch, IncomingMessage, TriggerEvent
from hobit_ax_agentos.storage import DeadlineWatchStore


class TriggerAgent:
    agent_id = "agent_hobit_trigger"

    def __init__(
        self,
        settings: AppSettings | None = None,
        watch_store: DeadlineWatchStore | None = None,
        adapter: Any | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.watch_store = watch_store or DeadlineWatchStore(self.settings.data_dir)
        self._adapter = adapter

    def register_deadline_watch(
        self,
        user_id: str,
        session_id: str,
        issue_type: str,
        deadline: date,
        reminder_window_days: int = 7,
        source: str = "manual",
        metadata: dict | None = None,
    ) -> DeadlineWatch:
        return self.watch_store.save(
            DeadlineWatch(
                watch_id=f"watch_{uuid4().hex}",
                user_id=user_id,
                session_id=session_id,
                issue_type=issue_type,
                deadline=deadline.isoformat(),
                reminder_window_days=reminder_window_days,
                source=source,
                metadata=dict(metadata or {}),
            )
        )

    def due_deadline_events(self, today: date | None = None) -> list[TriggerEvent]:
        today = today or date.today()
        events: list[TriggerEvent] = []
        for watch in self.watch_store.list_active_due(today):
            event = self.deadline_check(
                user_id=watch.user_id,
                session_id=watch.session_id,
                issue_type=watch.issue_type,
                deadline=date.fromisoformat(watch.deadline),
                today=today,
                metadata={
                    **watch.metadata,
                    "watch_id": watch.watch_id,
                    "source": watch.source,
                },
            )
            if event is None:
                continue
            events.append(event)
            self.watch_store.mark_triggered(watch.watch_id, today)
        return events

    def deadline_check(
        self,
        user_id: str,
        session_id: str,
        issue_type: str,
        deadline: date,
        today: date | None = None,
        metadata: dict | None = None,
    ) -> TriggerEvent | None:
        today = today or date.today()
        days_left = (deadline - today).days
        if days_left < 0 or days_left > 7:
            return None
        message = IncomingMessage(
            channel="trigger",
            user_id=user_id,
            session_id=session_id,
            text=(
                f"{issue_type} deadline is in {days_left} day(s). "
                "Would you like help checking requirements?"
            ),
            metadata={
                "trigger": "deadline_check",
                "issue_type": issue_type,
                "deadline": deadline.isoformat(),
                "days_left": days_left,
                **dict(metadata or {}),
            },
        )
        return TriggerEvent(
            trigger_id=f"trigger_{uuid4().hex}",
            event_type="deadline_check",
            user_id=user_id,
            session_id=session_id,
            message=message,
            metadata=message.metadata,
        )

    def regulation_change_events(self) -> list[TriggerEvent]:
        """Detect regulation source-document changes (via reconcile) and emit one
        TriggerEvent per user with an ACTIVE deadline watch on an affected issue_type.

        This is deliberately scoped to users who already opted into a watch — agentos
        has no system-wide user timeline store, so a full "walk every active user"
        sweep (as the architecture doc originally envisioned) isn't implementable yet.
        Best-effort: adapter failures yield no events rather than raising.
        """
        adapter = self._ensure_adapter()
        result = adapter.reconcile_regulations()
        affected = set(result.get("affected_issue_types") or [])
        if not result.get("has_changes") or not affected:
            return []

        events: list[TriggerEvent] = []
        seen: set[tuple[str, str]] = set()
        for watch in self.watch_store.list_all():
            if watch.status != "ACTIVE" or watch.issue_type not in affected:
                continue
            key = (watch.user_id, watch.issue_type)
            if key in seen:
                continue
            seen.add(key)
            message = IncomingMessage(
                channel="trigger",
                user_id=watch.user_id,
                session_id=watch.session_id,
                text=(
                    f"{watch.issue_type} 관련 규정이 변경되었습니다. "
                    "최신 내용을 확인해 드릴까요?"
                ),
                metadata={
                    "trigger": "regulation_changed",
                    "issue_type": watch.issue_type,
                    "needs_reingest": result.get("needs_reingest") or [],
                },
            )
            events.append(
                TriggerEvent(
                    trigger_id=f"trigger_{uuid4().hex}",
                    event_type="regulation_changed",
                    user_id=watch.user_id,
                    session_id=watch.session_id,
                    message=message,
                    metadata=message.metadata,
                )
            )
        return events

    def _ensure_adapter(self) -> Any:
        if self._adapter is None:
            from hobit_ax_agentos.adapters import RegulationRagAdapter

            self._adapter = RegulationRagAdapter(settings=self.settings)
        return self._adapter
