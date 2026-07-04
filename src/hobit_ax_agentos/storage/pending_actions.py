from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import PendingAction


class PendingActionStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "pending_actions.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, action: PendingAction) -> PendingAction:
        actions = {a.action_id: a for a in self.list_all()}
        actions[action.action_id] = action
        self._write_all(actions.values())
        return action

    def get(self, action_id: str) -> PendingAction | None:
        return next((a for a in self.list_all() if a.action_id == action_id), None)

    def list_by_user(self, user_id: str, limit: int = 50) -> list[PendingAction]:
        actions = [a for a in self.list_all() if a.user_id == user_id]
        return actions[-limit:]

    def list_by_session(self, session_id: str, limit: int = 50) -> list[PendingAction]:
        actions = [a for a in self.list_all() if a.session_id == session_id]
        return actions[-limit:]

    def list_pending(self, user_id: str | None = None) -> list[PendingAction]:
        return [
            a for a in self.list_all()
            if a.status == "PENDING" and (user_id is None or a.user_id == user_id)
        ]

    def submit(self, action_id: str) -> PendingAction | None:
        return self._set_status(action_id, "SUBMITTED")

    def cancel(self, action_id: str) -> PendingAction | None:
        return self._set_status(action_id, "CANCELLED")

    def list_all(self) -> list[PendingAction]:
        if not self.path.exists():
            return []
        actions: list[PendingAction] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            actions.append(PendingAction(**json.loads(line)))
        return actions

    def _set_status(self, action_id: str, status: str) -> PendingAction | None:
        from hobit_ax_agentos.models import utc_now
        actions = {a.action_id: a for a in self.list_all()}
        action = actions.get(action_id)
        if action is None:
            return None
        action.status = status  # type: ignore[assignment]
        action.updated_at = utc_now()
        self._write_all(actions.values())
        return action

    def _write_all(self, actions: Iterable[PendingAction]) -> None:
        lines = [json.dumps(a.to_dict(), ensure_ascii=False) for a in actions]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
