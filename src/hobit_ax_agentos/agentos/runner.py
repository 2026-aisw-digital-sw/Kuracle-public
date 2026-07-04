from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from hobit_ax_agentos.agentos.capabilities import (
    agent_capabilities,
    capability_id_for_agent,
    enabled_agent_capabilities,
)
from hobit_ax_agentos.agentos.contracts import validate_output_contract
from hobit_ax_agentos.agentos.plan_validation import (
    summarize_plan_execution,
    validate_lease_against_plan,
)
from hobit_ax_agentos.agents.escalation import EscalationAgent
from hobit_ax_agentos.agents.final_response import FinalResponseAgent
from hobit_ax_agentos.agents.knowledge import KnowledgeAgent
from hobit_ax_agentos.agents.persona import PersonaWorker
from hobit_ax_agentos.config import AppSettings, bootstrap_local_dependencies
from hobit_ax_agentos.models import AgentRunRecord, IncomingMessage, ServiceResult, utc_now
from hobit_ax_agentos.storage import (
    ConversationStore,
    IdempotencyStore,
    OutboxStore,
    PendingActionStore,
    PersonaStore,
    ProfileGateStore,
    ProfileStore,
    RegulationGapStore,
    RunStore,
)


logger = logging.getLogger(__name__)


Handler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(slots=True)
class ServiceRunner:
    settings: AppSettings = field(default_factory=AppSettings)
    kernel_client_factory: Callable[[], Any] | None = None
    knowledge_agent: KnowledgeAgent | None = None
    action_agent: object | None = None
    escalation_agent: EscalationAgent | None = None
    final_agent: FinalResponseAgent | None = None
    persona_worker: PersonaWorker | None = None
    conversation_store: ConversationStore | None = None
    outbox_store: OutboxStore | None = None
    persona_store: PersonaStore | None = None
    profile_store: ProfileStore | None = None
    profile_gate_store: ProfileGateStore | None = None
    pending_action_store: PendingActionStore | None = None
    regulation_gap_store: RegulationGapStore | None = None
    run_store: RunStore | None = None
    idempotency_store: IdempotencyStore | None = None
    _results: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        bootstrap_local_dependencies(self.settings)
        self.knowledge_agent = self.knowledge_agent or KnowledgeAgent(settings=self.settings)
        self.escalation_agent = self.escalation_agent or EscalationAgent(settings=self.settings)
        self.final_agent = self.final_agent or FinalResponseAgent()
        self.persona_worker = self.persona_worker or PersonaWorker()
        self.conversation_store = self.conversation_store or ConversationStore(self.settings.data_dir)
        self.outbox_store = self.outbox_store or OutboxStore(self.settings.data_dir)
        self.persona_store = self.persona_store or PersonaStore(self.settings.data_dir)
        self.profile_store = self.profile_store or ProfileStore(self.settings.data_dir)
        self.profile_gate_store = self.profile_gate_store or ProfileGateStore(self.settings.data_dir)
        self.pending_action_store = self.pending_action_store or PendingActionStore(self.settings.data_dir)
        self.regulation_gap_store = self.regulation_gap_store or RegulationGapStore(self.settings.data_dir)
        self.run_store = self.run_store or RunStore(self.settings.data_dir)
        self.idempotency_store = self.idempotency_store or IdempotencyStore(
            self.settings.data_dir
        )
        if self.settings.enable_action_agent and self.action_agent is None:
            from hobit_ax_agentos.agents.action import ActionAgent

            self.action_agent = ActionAgent()

    def run_message(self, message: IncomingMessage, timeout_seconds: float = 120.0) -> ServiceResult:
        from hobit_ax_agentos.agents.coordinator import CoordinatorAgent

        self._results = {}
        idempotency_key = self._idempotency_key(message)
        if idempotency_key:
            cached = self.idempotency_store.get(idempotency_key)  # type: ignore[union-attr]
            if cached:
                cached_run = self.run_store.get(cached["run_id"])  # type: ignore[union-attr]
                if cached_run:
                    return self._service_result_from_run(cached_run, reused=True)
        # Profile Gate: if the user is answering a profile follow-up, re-run original question.
        message = self._resolve_profile_gate(message)
        if not message.metadata.get("profile"):
            stored_profile = self.profile_store.get(message.user_id)  # type: ignore[union-attr]
            if stored_profile:
                message.metadata = {
                    **message.metadata,
                    "profile": {
                        "profile_type": stored_profile.profile_type,
                        "profile": stored_profile.profile,
                    },
                }
        history = [
            turn.to_dict()
            for turn in self.conversation_store.list_by_session(message.session_id)  # type: ignore[union-attr]
        ]
        persona = self.persona_worker.build(message, history=history)  # type: ignore[union-attr]
        self.persona_store.append(persona)  # type: ignore[union-attr]
        message.metadata = {
            **message.metadata,
            "persona": persona.to_dict(),
        }
        self.conversation_store.append_message(message)  # type: ignore[union-attr]
        coordinator = CoordinatorAgent(self.settings)
        coordination_plan = coordinator.create_plan(message, persona=persona)

        client = self._build_kernel_client()
        self._register_capabilities(client)
        graph_result = coordinator.plan(message)
        created = client.submit_graph(graph_result.graph)
        run_id = created["run_id"]
        self.run_store.save(  # type: ignore[union-attr]
            AgentRunRecord(
                run_id=run_id,
                session_id=message.session_id,
                user_id=message.user_id,
                channel=message.channel,
                state="RUNNING",
                coordination_plan_id=coordination_plan.plan_id,
                graph_id=graph_result.graph.to_dict().get("graph_id"),
            )
        )
        if idempotency_key:
            self.idempotency_store.save(  # type: ignore[union-attr]
                key=idempotency_key,
                run_id=run_id,
                session_id=message.session_id,
                user_id=message.user_id,
                channel=message.channel,
            )
        deadline = time.monotonic() + timeout_seconds
        worker_results: list[dict[str, Any]] = []
        lifecycle_events: list[dict[str, Any]] = [
            {
                "event": "run.started",
                "run_id": run_id,
                "plan_id": coordination_plan.plan_id,
                "at": utc_now(),
            }
        ]

        while time.monotonic() < deadline:
            run_summary = client.get_run(run_id)
            if run_summary["state"] in {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED"}:
                final = self._results.get("final_response")
                run_summary = {
                    **run_summary,
                    "plan_execution": summarize_plan_execution(
                        plan=coordination_plan,
                        worker_results=worker_results,
                    ),
                    "lifecycle_events": [
                        *lifecycle_events,
                        {
                            "event": "run.finished",
                            "run_id": run_id,
                            "state": str(run_summary["state"]),
                            "at": utc_now(),
                        },
                    ],
                }
                self.run_store.complete(  # type: ignore[union-attr]
                    run_id=run_id,
                    state=str(run_summary["state"]),
                    trace_id=run_summary.get("trace_id"),
                    final=final,
                    run_summary=run_summary,
                )
                final = self._post_process_run(
                    message=message,
                    final=final,
                    run_id=run_id,
                )
                if final and final.get("response"):
                    self.outbox_store.append_response(  # type: ignore[union-attr]
                        session_id=message.session_id,
                        user_id=message.user_id,
                        channel=str(final.get("delivery", {}).get("channel") or message.channel),
                        text=str(final["response"]),
                        payload=final,
                        run_id=run_id,
                        trace_id=run_summary.get("trace_id"),
                    )
                    self.conversation_store.append_assistant(  # type: ignore[union-attr]
                        session_id=message.session_id,
                        user_id=message.user_id,
                        text=str(final["response"]),
                        metadata={
                            "run_id": run_id,
                            "trace_id": run_summary.get("trace_id"),
                            "state": run_summary["state"],
                            "coordination_plan_id": coordination_plan.plan_id,
                        },
                    )
                return ServiceResult(
                    run_id=run_id,
                    trace_id=run_summary.get("trace_id"),
                    final=final,
                    run_summary=run_summary,
                    worker_results=worker_results,
                )

            handled = False
            agent_ids = [
                "agent_hobit_knowledge",
                "agent_hobit_escalation",
                "agent_hobit_final",
            ]
            if self.settings.enable_action_agent:
                agent_ids.insert(1, "agent_hobit_action")
            for agent_id in agent_ids:
                lease = client.lease_next_task(agent_id)
                if lease is None:
                    continue
                handled = True
                node_id = str(lease.node.get("node_id"))
                lease_event = {
                    "event": "node.leased",
                    "run_id": run_id,
                    "lease_id": lease.lease_id,
                    "node_id": node_id,
                    "agent_id": agent_id,
                    "trace_id": getattr(lease, "trace_id", None),
                    "at": utc_now(),
                }
                lifecycle_events.append(lease_event)
                try:
                    validate_lease_against_plan(
                        plan=coordination_plan,
                        node_id=node_id,
                        agent_id=agent_id,
                    )
                    lifecycle_events.append(
                        {
                            "event": "node.started",
                            "run_id": run_id,
                            "lease_id": lease.lease_id,
                            "node_id": node_id,
                            "agent_id": agent_id,
                            "at": utc_now(),
                        }
                    )
                    result = self._handle_lease(lease, message)
                    self._validate_result_contract(lease, result)
                    self._results[lease.node["node_id"]] = result
                    if node_id == "knowledge_query":
                        self._record_actual_classification(
                            coordinator.plan_store, coordination_plan, result
                        )
                    action_result = self._report_result(client, lease, result, message)
                    lifecycle_events.append(
                        {
                            "event": "node.completed",
                            "run_id": run_id,
                            "lease_id": lease.lease_id,
                            "node_id": node_id,
                            "agent_id": agent_id,
                            "at": utc_now(),
                        }
                    )
                    worker_result = {
                        "lease_id": lease.lease_id,
                        "node_id": node_id,
                        "agent_id": agent_id,
                        "contract_validated": True,
                        "handler_result": result,
                        "action_result": action_result,
                    }
                    worker_results.append(worker_result)
                    self.run_store.append_worker_result(run_id, worker_result)  # type: ignore[union-attr]
                except Exception as exc:
                    lifecycle_events.append(
                        {
                            "event": "node.failed",
                            "run_id": run_id,
                            "lease_id": lease.lease_id,
                            "node_id": node_id,
                            "agent_id": agent_id,
                            "error_type": exc.__class__.__name__,
                            "error": str(exc),
                            "at": utc_now(),
                        }
                    )
                    self._record_failed_run(
                        run_id=run_id,
                        state="FAILED",
                        trace_id=getattr(lease, "trace_id", None),
                        error=exc,
                        worker_results=worker_results,
                        lifecycle_events=lifecycle_events,
                        failed_node_id=node_id,
                        failed_agent_id=agent_id,
                    )
                    raise
            if not handled:
                time.sleep(0.05)

        self._record_failed_run(
            run_id=run_id,
            state="TIMED_OUT",
            trace_id=None,
            error=TimeoutError(f"AgentOS run {run_id} did not finish within {timeout_seconds}s"),
            worker_results=worker_results,
            lifecycle_events=[
                *lifecycle_events,
                {
                    "event": "run.timed_out",
                    "run_id": run_id,
                    "at": utc_now(),
                },
            ],
        )
        raise TimeoutError(f"AgentOS run {run_id} did not finish within {timeout_seconds}s")

    def _record_actual_classification(self, plan_store, plan, result: dict[str, Any]) -> None:
        """Patch the saved CoordinationPlan with the real LLM-derived intent once
        knowledge_query has run, so plan audits can compare it against the
        pre-execution "preliminary_classification" heuristic instead of relying on it
        as ground truth. Best-effort: plan persistence issues must not fail the run."""
        try:
            plan.routing_reasons["actual_classification"] = {
                "intent_mode": result.get("intent_mode"),
                "request_type": result.get("request_type"),
                "issue_types": result.get("issue_types") or [],
            }
            plan_store.save(plan)
        except Exception as exc:
            logger.warning(
                "[ServiceRunner] failed to record actual_classification for plan_id=%s: %s",
                getattr(plan, "plan_id", None),
                exc,
            )

    def _idempotency_key(self, message: IncomingMessage) -> str | None:
        key = message.metadata.get("idempotency_key")
        if key:
            return str(key)
        raw = message.metadata.get("raw")
        if isinstance(raw, dict) and raw.get("idempotency_key"):
            return str(raw["idempotency_key"])
        return None

    def _service_result_from_run(
        self,
        run: AgentRunRecord,
        reused: bool = False,
    ) -> ServiceResult:
        run_summary = dict(run.run_summary)
        if reused:
            run_summary["idempotency_reused"] = True
            run_summary["state"] = run.state
        return ServiceResult(
            run_id=run.run_id,
            trace_id=run.trace_id,
            final=run.final,
            run_summary=run_summary,
            worker_results=list(run.worker_results),
        )

    def dry_run_graph(self, message: IncomingMessage) -> dict[str, Any]:
        from hobit_ax_agentos.agents.coordinator import CoordinatorAgent

        graph_result = CoordinatorAgent(self.settings).plan(message)
        return graph_result.graph.to_dict()

    def _build_kernel_client(self):
        if self.kernel_client_factory is not None:
            return self.kernel_client_factory()
        from agentos_sdk import AgentOSClient

        return AgentOSClient(
            base_url=self.settings.kernel_base_url,
            api_token=self.settings.api_token,
            timeout=20.0,
        )

    def _record_failed_run(
        self,
        run_id: str,
        state: str,
        trace_id: str | None,
        error: Exception,
        worker_results: list[dict[str, Any]],
        lifecycle_events: list[dict[str, Any]] | None = None,
        failed_node_id: str | None = None,
        failed_agent_id: str | None = None,
    ) -> None:
        run_summary = {
            "state": state,
            "error_type": error.__class__.__name__,
            "error": str(error),
            "worker_results_count": len(worker_results),
            "lifecycle_events": lifecycle_events or [],
        }
        if failed_node_id:
            run_summary["failed_node_id"] = failed_node_id
        if failed_agent_id:
            run_summary["failed_agent_id"] = failed_agent_id
        self.run_store.complete(  # type: ignore[union-attr]
            run_id=run_id,
            state=state,
            trace_id=trace_id,
            final=None,
            run_summary=run_summary,
        )

    def _handle_lease(self, lease, message: IncomingMessage) -> dict[str, Any]:
        node_id = lease.node["node_id"]
        if node_id == "knowledge_query":
            return self.knowledge_agent.run({"message": message.to_dict()})  # type: ignore[union-attr]
        if node_id == "action_prepare":
            if self.action_agent is None:
                raise RuntimeError("ActionAgent is disabled")
            return self.action_agent.run(  # type: ignore[union-attr]
                {"knowledge": self._results.get("knowledge_query", {})}
            )
        if node_id == "escalation_prepare":
            return self.escalation_agent.run(  # type: ignore[union-attr]
                {
                    "knowledge": self._results.get("knowledge_query", {}),
                    "context": {
                        "user_id": message.user_id,
                        "session_id": message.session_id,
                        "run_id": lease.run_id,
                        "trace_id": lease.trace_id,
                    },
                }
            )
        if node_id == "final_response":
            return self.final_agent.run(  # type: ignore[union-attr]
                {
                    "channel": message.channel,
                    "knowledge": self._results.get("knowledge_query", {}),
                    "action": self._results.get("action_prepare", {}),
                    "escalation": self._results.get("escalation_prepare", {}),
                }
            )
        raise ValueError(f"unknown node id: {node_id}")

    def _report_result(
        self,
        client,
        lease,
        result: dict[str, Any],
        message: IncomingMessage,
    ) -> dict[str, Any]:
        from agentos_sdk import ActionIR, PolicyContext

        capability_id = capability_id_for_agent(lease.assigned_agent_id)
        action = ActionIR(
            run_id=lease.run_id,
            node_id=lease.node["node_id"],
            agent_id=lease.assigned_agent_id,
            capability_id=capability_id,
            action_type="TOOL_CALL",
            opcode="TOOL_CALL",
            args={
                "lease_id": lease.lease_id,
                "result": result,
                "node": lease.node,
            },
            policy_context=PolicyContext(
                tenant_id=self.settings.tenant_id,
                user_id=message.user_id,
                session_id=message.session_id,
                risk_class="LOW",
                severity="MEDIUM",
                labels={"app": "hobit-ax-agentos"},
            ),
        )
        return client.request_action(action)

    def _validate_result_contract(self, lease, result: dict[str, Any]) -> None:
        by_agent = {
            capability.agent_id: capability
            for capability in agent_capabilities(self.settings)
        }
        capability = by_agent.get(lease.assigned_agent_id)
        validate_output_contract(
            agent_id=lease.assigned_agent_id,
            node_id=str(lease.node.get("node_id")),
            result=result,
            schema=capability.output_schema if capability else None,
        )

    def _register_capabilities(self, client) -> None:
        from agentos_sdk import CapabilitySpec

        for capability in enabled_agent_capabilities(self.settings):
            client.register_capability(
                CapabilitySpec(
                    capability_id=capability.capability_id,
                    name=capability.name,
                    category=capability.category,
                    input_schema={},
                    output_schema=capability.output_schema or {},
                    trust_tier=capability.trust_tier,
                    required_permissions=[],
                )
            )

    # ── Profile Gate ─────────────────────────────────────────────────────────

    def _resolve_profile_gate(self, message: IncomingMessage) -> IncomingMessage:
        """If there's an active ProfileGateRecord for this session, treat the current
        message as the user's profile answer, then swap the message text to the original
        question and carry the profile answer as context."""
        gate = self.profile_gate_store.active_for_session(message.session_id)  # type: ignore[union-attr]
        if gate is None:
            return message
        gate = self.profile_gate_store.increment_retry(gate.gate_id)  # type: ignore[union-attr]
        if gate is None or gate.status == "EXPIRED":
            logger.info(
                "[ServiceRunner] ProfileGate %s expired after max retries", gate and gate.gate_id
            )
            return message
        self.profile_gate_store.resolve(gate.gate_id)  # type: ignore[union-attr]
        logger.info(
            "[ServiceRunner] ProfileGate %s resolved; re-running original question: %r",
            gate.gate_id,
            gate.original_text,
        )
        new_metadata = {
            **message.metadata,
            "profile_gate_response": message.text,
            "profile_gate_id": gate.gate_id,
            "profile_gate_missing_fields": gate.missing_fields,
        }
        from hobit_ax_agentos.models import IncomingMessage as IM
        return IM(
            channel=message.channel,
            user_id=message.user_id,
            text=gate.original_text,
            session_id=message.session_id,
            attachments=message.attachments,
            metadata=new_metadata,
        )

    def _post_process_run(
        self,
        message: IncomingMessage,
        final: dict[str, Any] | None,
        run_id: str,
    ) -> dict[str, Any] | None:
        """After a run completes, create ProfileGate if profile_gaps are present,
        store PendingAction if an action plan was produced, and log RegulationGaps
        for escalated runs."""
        if final is None:
            return final
        knowledge = self._results.get("knowledge_query", {})
        profile_gaps = knowledge.get("profile_gaps") or []
        if profile_gaps:
            gate = self._create_profile_gate(message, profile_gaps, run_id)
            follow_up = self._follow_up_for_gaps(profile_gaps)
            response = str(final.get("response") or "")
            final = {
                **final,
                "response": f"{response}\n\n{follow_up}".strip() if response else follow_up,
                "profile_gate": {
                    "gate_id": gate.gate_id,
                    "missing_fields": profile_gaps,
                    "follow_up_question": follow_up,
                },
            }
        action_result = self._results.get("action_prepare", {})
        action_plan = action_result.get("action_plan")
        if action_plan and isinstance(action_plan, dict):
            self._record_pending_action(message, action_plan, run_id)
        if knowledge.get("requires_human_review") and knowledge.get("regulation_gaps"):
            for gap_query in knowledge["regulation_gaps"]:
                issue_types = knowledge.get("issue_types") or []
                issue_type = issue_types[0] if issue_types else "unknown"
                self.regulation_gap_store.upsert(  # type: ignore[union-attr]
                    issue_type=issue_type,
                    query=str(gap_query),
                    user_id=message.user_id,
                    session_id=message.session_id,
                )
        return final

    def _create_profile_gate(
        self,
        message: IncomingMessage,
        missing_fields: list[str],
        run_id: str,
    ):
        import uuid
        from hobit_ax_agentos.models import ProfileGateRecord
        gate = ProfileGateRecord(
            gate_id=f"gate_{uuid.uuid4().hex}",
            session_id=message.session_id,
            user_id=message.user_id,
            original_text=message.metadata.get("original_text") or message.text,
            missing_fields=missing_fields,
            run_id=run_id,
        )
        self.profile_gate_store.save(gate)  # type: ignore[union-attr]
        logger.info(
            "[ServiceRunner] ProfileGate created: gate_id=%s missing=%s",
            gate.gate_id,
            missing_fields,
        )
        return gate

    def _follow_up_for_gaps(self, missing_fields: list[str]) -> str:
        _FIELD_QUESTIONS: dict[str, str] = {
            "college": "어느 단과대/학부 소속이신가요?",
            "college_name": "어느 단과대/학부 소속이신가요?",
            "department": "학과(부)가 어떻게 되시나요?",
            "department_name": "학과(부)가 어떻게 되시나요?",
            "year": "학번(입학 연도)이 어떻게 되시나요?",
            "year_of_admission": "학번(입학 연도)이 어떻게 되시나요?",
            "current_semester": "현재 몇 학기째 재학 중이신가요?",
            "semester": "현재 몇 학기째 재학 중이신가요?",
            "student_id": "학번이 어떻게 되시나요?",
            "is_transfer": "편입학생이신가요?",
            "double_major": "이중전공을 하고 계신가요?",
        }
        questions = []
        seen: set[str] = set()
        for field in missing_fields:
            q = _FIELD_QUESTIONS.get(field)
            if q and q not in seen:
                questions.append(q)
                seen.add(q)
        if not questions:
            questions = ["더 정확한 답변을 위해 추가 정보가 필요합니다. 학번, 학과, 단과대 등을 알려주시겠어요?"]
        return " ".join(questions)

    def _record_pending_action(
        self,
        message: IncomingMessage,
        action_plan: dict[str, Any],
        run_id: str,
    ) -> None:
        import uuid
        from hobit_ax_agentos.models import PendingAction
        action = PendingAction(
            action_id=f"pa_{uuid.uuid4().hex}",
            user_id=message.user_id,
            session_id=message.session_id,
            issue_type=str(action_plan.get("issue_type") or "unknown"),
            form_name=str(action_plan.get("form_name") or ""),
            action_plan=action_plan,
            run_id=run_id,
        )
        self.pending_action_store.save(action)  # type: ignore[union-attr]
        logger.info(
            "[ServiceRunner] PendingAction recorded: action_id=%s issue_type=%s",
            action.action_id,
            action.issue_type,
        )

