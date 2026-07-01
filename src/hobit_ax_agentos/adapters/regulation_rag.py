from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from hobit_ax_agentos.config import AppSettings, bootstrap_local_dependencies

logger = logging.getLogger(__name__)


class RegulationRagAdapter:
    """Thin adapter around the existing regulation_rag Supervisor.

    The adapter keeps all Hobit-specific RAG details outside AgentOS. AgentOS only sees
    a JSON-compatible result contract reported by KnowledgeAgent.

    Store/cache/trace-store dependencies are built once and reused across calls so that
    QueryCache/EvalCache actually warm (instead of being rebuilt — and therefore wiped —
    on every single query), and so a regulation_rag QueryTrace is recorded per query for
    the self-strengthening feedback loop (see TraceStore.add_feedback in EscalationStore).
    """

    _ENABLED_WORKERS = [
        "intake",
        "intent_triage",
        "issue_spotting",
        "regulation_evaluate",
        "answer_composer",
    ]

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        bootstrap_local_dependencies(self.settings)
        self._store: Any | None = None
        self._cache: Any | None = None
        self._eval_cache: Any | None = None
        self._trace_store: Any | None = None
        self._qdrant_client: Any | None = None
        self._kiwi: Any | None = None
        self._openai_client: Any | None = None

    def run_supervisor(
        self,
        query: str,
        profile: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            supervisor = self._build_supervisor(profile)
            state = supervisor.run(query)
            result = self._state_to_dict(state)
            trace_id = self._record_trace(state, session_id=session_id)
            if trace_id:
                result["regulation_rag_trace_id"] = trace_id
            result["cited_articles"] = self._decode_cited_rules(state)
            return result
        except Exception as exc:
            return {
                "raw_query": query,
                "workflow_status": "ESCALATED",
                "grounded_answer": {
                    "summary": "The regulation query could not be completed automatically and needs human review.",
                    "cited_rule_ids": [],
                    "unresolved_points": [str(exc)],
                    "regulation_gaps": [],
                },
                "adapter_error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

    def record_feedback(
        self,
        trace_id: str,
        signal: str = "neutral",
        comment: str | None = None,
        session_id: str | None = None,
    ) -> bool:
        """Attach a human-review outcome to a previously recorded QueryTrace.

        This is the write side of the self-strengthening loop: EscalationAgent calls
        this when an operator resolves a case, so TraceAnalyzer's issue_type/cited_rule
        success-rate aggregates eventually reflect human-reviewed outcomes too. Returns
        False (never raises) if the trace can't be found or feedback can't be recorded.
        """
        self._ensure_dependencies()
        try:
            from regulation_rag.domain.feedback import FeedbackEntry

            entry = FeedbackEntry(
                trace_id=trace_id,
                session_id=session_id,
                signal=signal if signal in {"positive", "negative", "neutral"} else "neutral",
                source="explicit",
                comment=comment,
            )
            recorded = self._trace_store.add_feedback(trace_id, entry)
            if recorded:
                self._trace_store.save_to_disk()
            return recorded
        except Exception as exc:
            logger.warning("[RegulationRagAdapter] failed to record feedback: %s", exc)
            return False

    def reconcile_regulations(self) -> dict[str, Any]:
        """Compare configs/regulation_manifest.yaml against ingested state and purge
        stale store/cache entries for any regulation whose source file changed.
        Never raises — callers (e.g. TriggerAgent) treat failures as "no changes"."""
        self._ensure_dependencies()
        try:
            from regulation_rag.store.manifest import RegulationManifest
            from regulation_rag.store.reconciler import reconcile

            # Capture rule_id -> issue_type before reconcile purges stale rules from
            # the store, so we can still report which issue_types were affected.
            rule_issue_by_id = {rule.rule_id: rule.issue_type for rule in self._store.rules.all()}

            manifest_path = (
                self.settings.regulation_rag_path / "configs" / "regulation_manifest.yaml"
            )
            store_dir = self.settings.regulation_rag_path / "data" / "store"
            manifest = RegulationManifest.load(manifest_path)
            result = reconcile(
                manifest=manifest,
                store=self._store,
                cache=self._cache,
                store_dir=str(store_dir),
                # regulation_manifest.yaml file: paths are relative to hobit-ax/, not
                # hobit-ax/regulation_rag/ (see the comment header in the yaml itself).
                project_root=self.settings.hobit_ax_repo_path,
            )
            affected_issue_types = sorted(
                {
                    rule_issue_by_id[rule_id]
                    for diff in result.diffs
                    for rule_id in diff.purged_rule_ids
                    if rule_id in rule_issue_by_id
                }
            )
            return {
                "has_changes": result.has_changes,
                "needs_reingest": result.needs_reingest,
                "cache_invalidated": result.cache_invalidated,
                "affected_issue_types": affected_issue_types,
                "diffs": [asdict(diff) for diff in result.diffs],
            }
        except Exception as exc:
            logger.warning("[RegulationRagAdapter] reconcile_regulations failed: %s", exc)
            return {"has_changes": False, "error": f"{type(exc).__name__}: {exc}"}

    def _decode_cited_rules(self, state: Any) -> list[dict[str, str]]:
        """cited_rule_ids를 실제 조항 레이블/내용으로 디코딩한다.

        subject_type 필터:
          인용된 규정 중 requester 유형과 불일치하는 subject_type의 조항은 제외한다.
          예) 학생이 휴학 관련 질문 → subject_type=faculty 조항(교직원 휴직 등)은 표시 안 함.
        """
        try:
            from regulation_rag.primitives.source_api import find_source_articles
            from regulation_rag.store.manifest import RegulationManifest

            answer = state.grounded_answer or {}
            rule_ids = answer.get("cited_rule_ids") or []
            if not rule_ids or self._store is None:
                return []

            # regulation_id → short_name 매핑 (manifest에서 로드)
            manifest_path = (
                self.settings.regulation_rag_path / "configs" / "regulation_manifest.yaml"
            )
            reg_name_map: dict[str, str] = {}
            try:
                manifest = RegulationManifest.load(manifest_path)
                reg_name_map = {
                    e.id: e.short_name
                    for e in manifest.all()
                    if e.short_name
                }
            except Exception:
                pass

            # requester 유형 → 허용할 subject_type 집합
            user_type = (state.user_context or {}).get("user_type", "unknown")
            _allowed: dict[str, set[str]] = {
                "student": {"student", "department", "office"},
                "staff":   {"staff", "faculty", "department", "office"},
                "faculty": {"faculty", "department", "office"},
                "public":  {"student", "staff", "faculty", "department", "office", "committee"},
            }
            allowed_subjects = _allowed.get(user_type, set(_allowed["public"]))

            seen: set[str] = set()
            result: list[dict[str, str]] = []
            for rule_id in rule_ids:
                rule = self._store.rules.get(rule_id)
                if rule is None:
                    continue
                if rule.subject_type.value not in allowed_subjects:
                    logger.debug(
                        "[RegulationRagAdapter] _decode_cited_rules: rule %s "
                        "subject_type=%s excluded for user_type=%s",
                        rule_id, rule.subject_type.value, user_type,
                    )
                    continue
                for article in find_source_articles(self._store, rule_id):
                    if article.node_id in seen or not article.label:
                        continue
                    seen.add(article.node_id)
                    doc_id = getattr(article, "document_id", None) or ""
                    regulation_name = reg_name_map.get(doc_id, doc_id)
                    result.append({
                        "node_id": article.node_id,
                        "label": article.label,
                        "regulation_name": regulation_name,
                        "content_preview": (article.content or "")[:200],
                    })
            return result
        except Exception as exc:
            logger.warning("[RegulationRagAdapter] _decode_cited_rules failed: %s", exc)
            return []

    def build_user_profile(self, profile: dict[str, Any] | None) -> Any | None:
        """Public wrapper so callers outside this module (e.g. persona prefetch) can
        reuse the same dict -> regulation_rag UserProfile conversion KnowledgeAgent uses."""
        return self._build_user_profile(profile)

    def get_trace_store(self) -> Any:
        """Expose the shared, disk-persisted TraceStore for read-side consumers
        (e.g. persona prefetch's build_persona, which needs session trace history)."""
        self._ensure_dependencies()
        return self._trace_store

    def get_supervisor(self, profile: dict[str, Any] | None = None) -> Any:
        """Expose a Supervisor bound to the shared store/cache for callers that need
        to drive it directly (e.g. persona prefetch's prefetch_background)."""
        return self._build_supervisor(profile)

    def _ensure_dependencies(self) -> None:
        if self._store is not None:
            return
        from regulation_rag.cache import QueryCache
        from regulation_rag.cache.eval_cache import EvalCache
        from regulation_rag.store.in_memory import InMemoryStore
        from regulation_rag.store.trace_store import TraceStore

        store = InMemoryStore()
        store_dir = self.settings.regulation_rag_path / "data" / "store"
        taxonomy = self.settings.regulation_rag_path / "configs" / "taxonomy" / "issue_types.json"
        if store_dir.exists():
            store.restore(str(store_dir))
        if taxonomy.exists():
            store.taxonomy.load_from_file(str(taxonomy))

        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._store = store
        self._cache = QueryCache(ttl_seconds=3600)
        self._eval_cache = EvalCache(ttl_seconds=7200)
        self._trace_store = TraceStore(
            persist_path=str(self.settings.data_dir / "regulation_rag_traces.json")
        )
        self._qdrant_client, self._kiwi, self._openai_client = self._build_hybrid_clients()

    def _build_hybrid_clients(self) -> tuple[Any | None, Any | None, Any | None]:
        """Build the optional dense+sparse retrieval backend. Prefers a local
        file-mode Qdrant store (regulation_rag's own default — no server needed) and
        only uses a remote URL if HOBIT_QDRANT_URL is explicitly set, matching
        regulation_rag/api/main.py's own qdrant_url/qdrant_path fallback order.
        openai_api_key must also be set; if anything is missing or fails to
        import/connect, hybrid retrieval is silently skipped and Supervisor falls
        back to sparse-only content lookup."""
        if not self.settings.openai_api_key:
            return None, None, None
        if not (self.settings.qdrant_url or self.settings.qdrant_local_path.exists()):
            return None, None, None
        try:
            import openai
            from kiwipiepy import Kiwi
            from qdrant_client import QdrantClient

            if self.settings.qdrant_url:
                qdrant_client = QdrantClient(url=self.settings.qdrant_url, timeout=10)
            else:
                qdrant_client = QdrantClient(path=str(self.settings.qdrant_local_path))
            kiwi = Kiwi()
            openai_client = openai.OpenAI(api_key=self.settings.openai_api_key)
            return qdrant_client, kiwi, openai_client
        except Exception as exc:
            logger.warning(
                "[RegulationRagAdapter] hybrid retrieval unavailable, falling back to "
                "sparse-only: %s",
                exc,
            )
            return None, None, None

    def _build_user_profile(self, profile: dict[str, Any] | None) -> Any | None:
        if not profile:
            return None
        from regulation_rag.domain.user_profile import (
            FacultyProfile,
            PublicProfile,
            StaffProfile,
            StudentProfile,
        )

        profile_type = str(profile.get("profile_type") or profile.get("user_type") or "public")
        fields = profile.get("profile")
        fields = fields if isinstance(fields, dict) else profile
        # from_dict() calls int()/float() on Optional numeric fields; empty strings from
        # the frontend form cause ValueError → user_profile=None → evaluation silently skipped.
        # Normalize empty strings to None before handing off to from_dict().
        fields = {k: (None if v == "" else v) for k, v in fields.items()}
        factory = {
            "student": StudentProfile.from_dict,
            "staff": StaffProfile.from_dict,
            "faculty": FacultyProfile.from_dict,
            "public": PublicProfile.from_dict,
        }.get(profile_type, PublicProfile.from_dict)
        try:
            return factory(fields)
        except Exception as exc:
            logger.warning(
                "[RegulationRagAdapter] failed to build UserProfile (type=%s): %s",
                profile_type,
                exc,
            )
            return None

    def _build_supervisor(self, profile: dict[str, Any] | None = None):
        from regulation_rag.workers.supervisor import Supervisor

        self._ensure_dependencies()
        return Supervisor(
            store=self._store,
            user_profile=self._build_user_profile(profile),
            enabled_workers=self._ENABLED_WORKERS,
            cache=self._cache,
            eval_cache=self._eval_cache,
            qdrant_client=self._qdrant_client,
            kiwi=self._kiwi,
            openai_client=self._openai_client,
            qdrant_collection=self.settings.qdrant_collection,
        )

    def _record_trace(self, state: Any, session_id: str | None) -> str | None:
        if self._trace_store is None:
            return None
        try:
            from regulation_rag.domain.feedback import QueryTrace

            answer = state.grounded_answer or {}
            issue_types = [
                issue.get("issue_type", "") for issue in (state.issue_graph or [])
            ]
            trace = QueryTrace(
                trace_id=state.request_id,
                session_id=session_id,
                query=state.raw_query,
                normalized_query=state.normalized_query or state.raw_query,
                issue_types=[it for it in issue_types if it],
                cited_rule_ids=answer.get("cited_rule_ids", []),
                answer_snippet=str(answer.get("summary", ""))[:200],
                query_class="regulation",
                intent_mode=(state.parsed_intent or {}).get("intent_mode"),
                workflow_status=state.workflow_status.value,
                worker_timings_ms=state.worker_timings_ms,
                regulation_gaps=answer.get("regulation_gaps", []),
            )
            self._trace_store.record(trace)
            self._trace_store.save_to_disk()
            return trace.trace_id
        except Exception as exc:
            logger.warning("[RegulationRagAdapter] failed to record QueryTrace: %s", exc)
            return None

    def _state_to_dict(self, state: Any) -> dict[str, Any]:
        if hasattr(state, "to_dict"):
            return self._json_safe(state.to_dict())
        if is_dataclass(state):
            return self._json_safe(asdict(state))
        if isinstance(state, dict):
            return self._json_safe(state)
        return {"value": self._json_safe(state)}

    def _json_safe(self, value: Any) -> Any:
        if is_dataclass(value):
            return self._json_safe(asdict(value))
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(item) for item in value]
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)
