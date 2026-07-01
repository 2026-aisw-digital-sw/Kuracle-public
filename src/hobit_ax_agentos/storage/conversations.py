from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from hobit_ax_agentos.models import ConversationTurn, IncomingMessage


class ConversationStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "conversation_turns.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def append_message(self, message: IncomingMessage) -> ConversationTurn:
        turn = ConversationTurn(
            turn_id=f"turn_{uuid4().hex}",
            session_id=message.session_id,
            user_id=message.user_id,
            channel=message.channel,
            text=message.text,
            role="USER",
            metadata=message.metadata,
        )
        self.append(turn)
        return turn

    def append_assistant(
        self,
        session_id: str,
        user_id: str,
        text: str,
        metadata: dict | None = None,
    ) -> ConversationTurn:
        turn = ConversationTurn(
            turn_id=f"turn_{uuid4().hex}",
            session_id=session_id,
            user_id=user_id,
            channel="agentos",
            text=text,
            role="ASSISTANT",
            metadata=dict(metadata or {}),
        )
        self.append(turn)
        return turn

    def append(self, turn: ConversationTurn) -> ConversationTurn:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(turn.to_dict(), ensure_ascii=False) + "\n")
        return turn

    def list_by_session(self, session_id: str, limit: int = 50) -> list[ConversationTurn]:
        turns = [
            turn
            for turn in self.list_all()
            if turn.session_id == session_id
        ]
        return turns[-limit:]

    def list_all(self) -> list[ConversationTurn]:
        if not self.path.exists():
            return []
        turns: list[ConversationTurn] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            turns.append(ConversationTurn(**json.loads(line)))
        return turns
