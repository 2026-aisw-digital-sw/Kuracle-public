from __future__ import annotations

from datetime import datetime, timezone

from hobit_ax_agentos.models import ConversationTurn
from hobit_ax_agentos.services.retention import RetentionService
from hobit_ax_agentos.storage import ConversationStore


def test_retention_prune_dry_run_does_not_modify_files(tmp_path) -> None:
    ConversationStore(tmp_path).append(
        ConversationTurn(
            turn_id="turn_old",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            text="old",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    before = (tmp_path / "conversation_turns.jsonl").read_text(encoding="utf-8")

    result = RetentionService(tmp_path).prune(
        older_than_days=30,
        dry_run=True,
        now=datetime(2026, 6, 30, tzinfo=timezone.utc),
    )
    after = (tmp_path / "conversation_turns.jsonl").read_text(encoding="utf-8")

    assert result["dry_run"] is True
    assert result["remove_count"] == 1
    assert before == after


def test_retention_prune_removes_only_old_records(tmp_path) -> None:
    store = ConversationStore(tmp_path)
    store.append(
        ConversationTurn(
            turn_id="turn_old",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            text="old",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    store.append(
        ConversationTurn(
            turn_id="turn_new",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            text="new",
            created_at="2026-06-29T00:00:00+00:00",
        )
    )

    result = RetentionService(tmp_path).prune(
        older_than_days=30,
        dry_run=False,
        now=datetime(2026, 6, 30, tzinfo=timezone.utc),
    )
    turns = ConversationStore(tmp_path).list_all()

    assert result["dry_run"] is False
    assert result["remove_count"] == 1
    assert [turn.turn_id for turn in turns] == ["turn_new"]
