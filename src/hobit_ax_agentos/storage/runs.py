from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import AgentRunRecord, utc_now
from hobit_ax_agentos.storage.locking import file_lock


class RunStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "agent_runs.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, run: AgentRunRecord) -> AgentRunRecord:
        with file_lock(self.path):
            runs = {item.run_id: item for item in self._read_all_unlocked()}
            run.updated_at = utc_now()
            runs[run.run_id] = run
            self._write_all_unlocked(runs.values())
        return run

    def get(self, run_id: str) -> AgentRunRecord | None:
        return next((run for run in self.list_all() if run.run_id == run_id), None)

    def list_by_session(
        self,
        session_id: str,
        limit: int = 50,
        state: str | None = None,
    ) -> list[AgentRunRecord]:
        runs = [run for run in self.list_all() if run.session_id == session_id]
        if state:
            runs = [run for run in runs if run.state == state.upper()]
        return runs[-limit:]

    def list_by_state(
        self,
        state: str | None = None,
        limit: int = 50,
    ) -> list[AgentRunRecord]:
        runs = self.list_all()
        if state:
            runs = [run for run in runs if run.state == state.upper()]
        return runs[-limit:]

    def append_worker_result(
        self,
        run_id: str,
        worker_result: dict,
    ) -> AgentRunRecord:
        run = self._require(run_id)
        run.worker_results.append(worker_result)
        return self.save(run)

    def complete(
        self,
        run_id: str,
        state: str,
        trace_id: str | None,
        final: dict | None,
        run_summary: dict,
    ) -> AgentRunRecord:
        run = self._require(run_id)
        run.state = state
        run.trace_id = trace_id
        run.final = final
        run.run_summary = run_summary
        return self.save(run)

    def list_all(self) -> list[AgentRunRecord]:
        with file_lock(self.path):
            return self._read_all_unlocked()

    def _read_all_unlocked(self) -> list[AgentRunRecord]:
        if not self.path.exists():
            return []
        runs: list[AgentRunRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            runs.append(AgentRunRecord(**json.loads(line)))
        return runs

    def _write_all_unlocked(self, runs: Iterable[AgentRunRecord]) -> None:
        lines = [json.dumps(run.to_dict(), ensure_ascii=False) for run in runs]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _require(self, run_id: str) -> AgentRunRecord:
        run = self.get(run_id)
        if run is None:
            raise KeyError(run_id)
        return run
