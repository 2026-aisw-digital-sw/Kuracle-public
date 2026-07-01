from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from hobit_ax_agentos.config import AppSettings, bootstrap_local_dependencies
from hobit_ax_agentos.models import IncomingMessage


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="hobit-agentos")
    sub = parser.add_subparsers(dest="command", required=True)
    query = sub.add_parser("query", help="Run a Hobit AX query through AgentOS")
    query.add_argument("text")
    query.add_argument("--channel", default="api")
    query.add_argument("--user-id", default=None)
    query.add_argument("--session-id", default=None)
    query.add_argument("--dry-run", action="store_true")
    query.add_argument("--timeout", type=float, default=120.0)
    gateway = sub.add_parser("gateway", help="Normalize and optionally run a channel payload")
    gateway.add_argument("channel")
    gateway.add_argument("--payload", default=None)
    gateway.add_argument("--payload-file", default=None)
    gateway.add_argument("--dry-run", action="store_true")
    gateway.add_argument("--run", action="store_true")
    gateway.add_argument("--timeout", type=float, default=120.0)
    sub.add_parser("doctor", help="Check local AgentOS and Hobit AX dependencies")
    integration_probe = sub.add_parser("integration-probe", help="Probe real AgentOS/RAG integrations")
    integration_probe.add_argument("--rag-query", default="복수전공 신청 기간 알려줘")
    smoke_e2e = sub.add_parser("smoke-e2e", help="Run an end-to-end backend smoke test")
    smoke_e2e.add_argument("--query", default="double major application deadline")
    smoke_e2e.add_argument("--channel", default="api")
    smoke_e2e.add_argument("--user-id", default=None)
    smoke_e2e.add_argument("--session-id", default=None)
    smoke_e2e.add_argument("--timeout", type=float, default=120.0)
    smoke_e2e.add_argument("--render-channel", default=None)
    sub.add_parser("config", help="Show sanitized runtime configuration")
    profile_set = sub.add_parser(
        "profile-set", help="Create or update a stored regulation_rag user profile"
    )
    profile_set.add_argument("user_id")
    profile_set.add_argument(
        "--type",
        dest="profile_type",
        required=True,
        choices=["student", "staff", "faculty", "public"],
    )
    profile_set.add_argument(
        "--field",
        dest="fields",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Repeatable profile field, e.g. --field grade=3 --field scope=undergraduate",
    )
    profile_set.add_argument(
        "--json",
        dest="profile_json",
        default=None,
        help="Full profile fields as a JSON object (merged with --field; --field wins on conflict)",
    )
    profile_get = sub.add_parser("profile-get", help="Show a stored user profile")
    profile_get.add_argument("user_id")
    persona = sub.add_parser("persona", help="Build deterministic persona context")
    persona.add_argument("text")
    persona.add_argument("--user-id", default=None)
    persona.add_argument("--session-id", default=None)
    persona.add_argument("--save", action="store_true")
    persona_prefetch = sub.add_parser(
        "persona-prefetch",
        help="LLM-predict likely follow-up questions and warm the QueryCache in the background",
    )
    persona_prefetch.add_argument("text")
    persona_prefetch.add_argument("--user-id", default=None)
    persona_prefetch.add_argument("--session-id", default=None)
    personas = sub.add_parser("personas", help="Show stored persona snapshots")
    personas.add_argument("--session-id", default=None)
    personas.add_argument("--limit", type=int, default=20)
    trigger = sub.add_parser("deadline-trigger", help="Create a deadline trigger event")
    trigger.add_argument("issue_type")
    trigger.add_argument("deadline")
    trigger.add_argument("--today", default=None)
    trigger.add_argument("--user-id", default=None)
    trigger.add_argument("--session-id", default=None)
    watch_deadline = sub.add_parser("watch-deadline", help="Register a deadline watch")
    watch_deadline.add_argument("issue_type")
    watch_deadline.add_argument("deadline")
    watch_deadline.add_argument("--window-days", type=int, default=7)
    watch_deadline.add_argument("--user-id", default=None)
    watch_deadline.add_argument("--session-id", default=None)
    deadline_watches = sub.add_parser("deadline-watches", help="Show stored deadline watches")
    deadline_watches.add_argument("--session-id", default=None)
    deadline_watches.add_argument("--limit", type=int, default=20)
    due_deadline_triggers = sub.add_parser("due-deadline-triggers", help="Emit due deadline triggers")
    due_deadline_triggers.add_argument("--today", default=None)
    due_deadline_triggers.add_argument("--dispatch", action="store_true")
    due_deadline_triggers.add_argument("--timeout", type=float, default=120.0)
    regulation_refresh = sub.add_parser(
        "regulation-refresh",
        help="Reconcile regulation source files and emit change-notification triggers",
    )
    regulation_refresh.add_argument("--dispatch", action="store_true")
    regulation_refresh.add_argument("--timeout", type=float, default=120.0)
    sessions = sub.add_parser("sessions", help="List known sessions")
    sessions.add_argument("--limit", type=int, default=50)
    history = sub.add_parser("history", help="Show stored conversation turns")
    history.add_argument("--session-id", default=None)
    history.add_argument("--limit", type=int, default=20)
    summary = sub.add_parser("summary", help="Show session state summary")
    summary.add_argument("--session-id", default=None)
    summary.add_argument("--limit", type=int, default=10)
    timeline = sub.add_parser("timeline", help="Show session event timeline")
    timeline.add_argument("--session-id", default=None)
    timeline.add_argument("--limit", type=int, default=50)
    export_session = sub.add_parser("export-session", help="Export one session as JSON")
    export_session.add_argument("--session-id", default=None)
    export_session.add_argument("--output", default=None)
    export_session.add_argument("--limit", type=int, default=1000000)
    sub.add_parser("storage-stats", help="Show local JSONL storage statistics")
    sub.add_parser("storage-audit", help="Validate local JSONL storage records")
    prune_storage = sub.add_parser("prune-storage", help="Prune old JSONL records")
    prune_storage.add_argument("--older-than-days", type=int, required=True)
    prune_storage.add_argument("--apply", action="store_true")
    sub.add_parser("metrics", help="Show operational status metrics")
    alerts = sub.add_parser("alerts", help="Show operational alerts")
    alerts.add_argument("--running-minutes", type=int, default=10)
    alerts.add_argument("--job-minutes", type=int, default=10)
    alerts.add_argument("--delivery-minutes", type=int, default=10)
    alerts.add_argument("--escalation-minutes", type=int, default=30)
    alerts.add_argument("--deadline-days", type=int, default=3)
    agents = sub.add_parser("agents", help="Show AgentOS agent capability manifest")
    agents.add_argument("--enabled-only", action="store_true")
    jobs = sub.add_parser("jobs", help="Show async submit jobs")
    jobs.add_argument("--status", default=None)
    jobs.add_argument("--limit", type=int, default=20)
    job = sub.add_parser("job", help="Show one async submit job")
    job.add_argument("job_id")
    run_job = sub.add_parser("run-job", help="Run one queued async job")
    run_job.add_argument("job_id")
    run_job.add_argument("--timeout", type=float, default=None)
    run_jobs = sub.add_parser("run-jobs", help="Run queued async jobs")
    run_jobs.add_argument("--limit", type=int, default=10)
    run_jobs.add_argument("--watch", action="store_true")
    run_jobs.add_argument("--interval-seconds", type=float, default=1.0)
    run_jobs.add_argument("--max-iterations", type=int, default=None)
    run_jobs.add_argument("--stop-when-idle", action="store_true")
    run_jobs.add_argument("--requeue-stale-minutes", type=int, default=None)
    requeue_jobs = sub.add_parser("requeue-stale-jobs", help="Requeue stale RUNNING async jobs")
    requeue_jobs.add_argument("--older-than-minutes", type=int, default=30)
    requeue_jobs.add_argument("--limit", type=int, default=50)
    retry_job = sub.add_parser("retry-job", help="Retry a failed or cancelled async job")
    retry_job.add_argument("job_id")
    retry_job.add_argument("--timeout", type=float, default=None)
    cancel_job = sub.add_parser("cancel-job", help="Cancel a queued async job")
    cancel_job.add_argument("job_id")
    cancel_job.add_argument("--reason", default=None)
    outbox = sub.add_parser("outbox", help="Show outbound deliveries")
    outbox.add_argument("--session-id", default=None)
    outbox.add_argument("--status", default=None)
    outbox.add_argument("--limit", type=int, default=20)
    sent_delivery = sub.add_parser("mark-delivery-sent", help="Mark an outbound delivery as sent")
    sent_delivery.add_argument("delivery_id")
    failed_delivery = sub.add_parser("mark-delivery-failed", help="Mark an outbound delivery as failed")
    failed_delivery.add_argument("delivery_id")
    failed_delivery.add_argument("--error", default=None)
    dispatch_delivery = sub.add_parser("dispatch-delivery", help="Dispatch one outbound delivery")
    dispatch_delivery.add_argument("delivery_id")
    render_delivery = sub.add_parser("render-delivery", help="Render one outbound delivery payload")
    render_delivery.add_argument("delivery_id")
    render_delivery.add_argument("--channel", default=None)
    dispatch_outbox = sub.add_parser("dispatch-outbox", help="Dispatch pending outbound deliveries")
    dispatch_outbox.add_argument("--limit", type=int, default=50)
    plans = sub.add_parser("plans", help="Show stored coordination plans")
    plans.add_argument("--session-id", default=None)
    plans.add_argument("--limit", type=int, default=20)
    runs = sub.add_parser("runs", help="Show stored AgentOS runs")
    runs.add_argument("--session-id", default=None)
    runs.add_argument("--state", default=None)
    runs.add_argument("--all", action="store_true")
    runs.add_argument("--limit", type=int, default=20)
    run = sub.add_parser("run", help="Show one stored AgentOS run")
    run.add_argument("run_id")
    run_trace = sub.add_parser("run-trace", help="Show a joined run trace package")
    run_trace.add_argument("run_id")
    run_trace.add_argument("--conversation-limit", type=int, default=20)
    retry_run = sub.add_parser("retry-run", help="Retry a failed AgentOS run")
    retry_run.add_argument("run_id")
    retry_run.add_argument("--timeout", type=float, default=120.0)
    cancel_run = sub.add_parser("cancel-run", help="Cancel a pending/running/blocked AgentOS run")
    cancel_run.add_argument("run_id")
    cancel_run.add_argument("--reason", default=None)
    escalations = sub.add_parser("escalations", help="List escalation cases")
    escalations.add_argument("--status", default=None)
    ack = sub.add_parser("ack-escalation", help="Acknowledge an escalation case")
    ack.add_argument("escalation_id")
    assign = sub.add_parser("assign-escalation", help="Assign an escalation case")
    assign.add_argument("escalation_id")
    assign.add_argument("assignee")
    note = sub.add_parser("note-escalation", help="Add a note to an escalation case")
    note.add_argument("escalation_id")
    note.add_argument("text")
    note.add_argument("--author", default="operator")
    note.add_argument("--visibility", default="internal")
    resolve = sub.add_parser("resolve-escalation", help="Resolve an escalation case")
    resolve.add_argument("escalation_id")
    resolve.add_argument(
        "--signal",
        choices=["positive", "negative", "neutral"],
        default="neutral",
        help="Review outcome fed back into regulation_rag's trace feedback loop",
    )
    resolve.add_argument("--comment", default=None)
    args = parser.parse_args()

    settings = AppSettings()
    bootstrap_local_dependencies(settings)

    if args.command == "query":
        from hobit_ax_agentos.agentos.runner import ServiceRunner

        message = IncomingMessage(
            channel=args.channel,
            user_id=args.user_id or settings.default_user_id,
            text=args.text,
            session_id=args.session_id or settings.default_session_id,
        )
        runner = ServiceRunner(settings=settings)
        if args.dry_run:
            print(json.dumps(runner.dry_run_graph(message), ensure_ascii=False, indent=2))
            return
        result = runner.run_message(message, timeout_seconds=args.timeout)
        print(json.dumps(_service_result_to_dict(result), ensure_ascii=False, indent=2))
    elif args.command == "gateway":
        from hobit_ax_agentos.agentos.runner import ServiceRunner
        from hobit_ax_agentos.agents.channel_gateway import ChannelGateway
        from hobit_ax_agentos.agents.coordinator import CoordinatorAgent

        payload = _load_payload(args.payload, args.payload_file)
        message = ChannelGateway(settings).normalize(args.channel, payload)
        output = {
            "message": message.to_dict(),
            "classification": CoordinatorAgent(settings).classify(message),
        }
        runner = ServiceRunner(settings=settings)
        if args.dry_run:
            output["graph"] = runner.dry_run_graph(message)
        if args.run:
            result = runner.run_message(message, timeout_seconds=args.timeout)
            output["result"] = _service_result_to_dict(result)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif args.command == "doctor":
        from hobit_ax_agentos.services.doctor import DoctorService

        print(json.dumps(DoctorService(settings).report(), ensure_ascii=False, indent=2))
    elif args.command == "integration-probe":
        from hobit_ax_agentos.services.integration_probe import IntegrationProbeService

        print(
            json.dumps(
                IntegrationProbeService(settings).report(rag_query=args.rag_query),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "smoke-e2e":
        from hobit_ax_agentos.services.e2e_smoke import E2ESmokeService

        result = E2ESmokeService(settings).run(
            query=args.query,
            channel=args.channel,
            user_id=args.user_id,
            session_id=args.session_id,
            timeout_seconds=args.timeout,
            render_channel=args.render_channel,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "config":
        from hobit_ax_agentos.services.config_snapshot import ConfigSnapshotService

        print(json.dumps(ConfigSnapshotService(settings).snapshot(), ensure_ascii=False, indent=2))
    elif args.command == "profile-set":
        from hobit_ax_agentos.models import UserProfileRecord
        from hobit_ax_agentos.storage import ProfileStore

        profile: dict = {}
        if args.profile_json:
            try:
                profile.update(json.loads(args.profile_json))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON in --json: {exc}") from exc
        for raw in args.fields:
            if "=" not in raw:
                raise SystemExit(f"--field expects KEY=VALUE, got: {raw}")
            key, _, value = raw.partition("=")
            profile[key] = _parse_field_value(value)
        record = ProfileStore(settings.data_dir).upsert(
            UserProfileRecord(user_id=args.user_id, profile_type=args.profile_type, profile=profile)
        )
        print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "profile-get":
        from hobit_ax_agentos.storage import ProfileStore

        record = ProfileStore(settings.data_dir).get(args.user_id)
        print(json.dumps(record.to_dict() if record else None, ensure_ascii=False, indent=2))
    elif args.command == "persona":
        from hobit_ax_agentos.agents.persona import PersonaWorker
        from hobit_ax_agentos.storage import PersonaStore

        message = IncomingMessage(
            channel="cli",
            user_id=args.user_id or settings.default_user_id,
            text=args.text,
            session_id=args.session_id or settings.default_session_id,
        )
        snapshot = PersonaWorker().build(message)
        if args.save:
            PersonaStore(settings.data_dir).append(snapshot)
        print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "persona-prefetch":
        from hobit_ax_agentos.services.persona_prefetch import PersonaPrefetchService
        from hobit_ax_agentos.storage import PersonaStore

        message = IncomingMessage(
            channel="cli",
            user_id=args.user_id or settings.default_user_id,
            text=args.text,
            session_id=args.session_id or settings.default_session_id,
        )
        snapshot = PersonaPrefetchService(settings).prefetch(message)
        PersonaStore(settings.data_dir).append(snapshot)
        print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "personas":
        from hobit_ax_agentos.storage import PersonaStore

        session_id = args.session_id or settings.default_session_id
        snapshots = PersonaStore(settings.data_dir).list_by_session(session_id, args.limit)
        print(json.dumps([snapshot.to_dict() for snapshot in snapshots], ensure_ascii=False, indent=2))
    elif args.command == "deadline-trigger":
        from hobit_ax_agentos.agents.trigger import TriggerAgent

        event = TriggerAgent().deadline_check(
            user_id=args.user_id or settings.default_user_id,
            session_id=args.session_id or settings.default_session_id,
            issue_type=args.issue_type,
            deadline=date.fromisoformat(args.deadline),
            today=date.fromisoformat(args.today) if args.today else None,
        )
        print(json.dumps(event.to_dict() if event else None, ensure_ascii=False, indent=2))
    elif args.command == "watch-deadline":
        from hobit_ax_agentos.agents.trigger import TriggerAgent

        watch = TriggerAgent(settings).register_deadline_watch(
            user_id=args.user_id or settings.default_user_id,
            session_id=args.session_id or settings.default_session_id,
            issue_type=args.issue_type,
            deadline=date.fromisoformat(args.deadline),
            reminder_window_days=args.window_days,
            source="cli",
        )
        print(json.dumps(watch.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "deadline-watches":
        from hobit_ax_agentos.storage import DeadlineWatchStore

        session_id = args.session_id or settings.default_session_id
        watches = DeadlineWatchStore(settings.data_dir).list_by_session(session_id, args.limit)
        print(json.dumps([watch.to_dict() for watch in watches], ensure_ascii=False, indent=2))
    elif args.command == "due-deadline-triggers":
        from hobit_ax_agentos.agents.trigger import TriggerAgent
        from hobit_ax_agentos.services.trigger_dispatcher import TriggerDispatcher

        today = date.fromisoformat(args.today) if args.today else None
        if args.dispatch:
            dispatches = TriggerDispatcher(settings).dispatch_due_deadline_events(
                today=today,
                timeout_seconds=args.timeout,
            )
            print(json.dumps(dispatches, ensure_ascii=False, indent=2))
            return
        events = TriggerAgent(settings).due_deadline_events(today=today)
        print(json.dumps([event.to_dict() for event in events], ensure_ascii=False, indent=2))
    elif args.command == "regulation-refresh":
        from hobit_ax_agentos.agents.trigger import TriggerAgent
        from hobit_ax_agentos.services.trigger_dispatcher import TriggerDispatcher

        if args.dispatch:
            dispatches = TriggerDispatcher(settings).dispatch_regulation_change_events(
                timeout_seconds=args.timeout,
            )
            print(json.dumps(dispatches, ensure_ascii=False, indent=2))
            return
        events = TriggerAgent(settings).regulation_change_events()
        print(json.dumps([event.to_dict() for event in events], ensure_ascii=False, indent=2))
    elif args.command == "sessions":
        from hobit_ax_agentos.services.session_directory import SessionDirectoryService

        result = SessionDirectoryService(settings.data_dir).list_sessions(limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "history":
        from hobit_ax_agentos.storage import ConversationStore

        session_id = args.session_id or settings.default_session_id
        turns = ConversationStore(settings.data_dir).list_by_session(session_id, limit=args.limit)
        print(json.dumps([turn.to_dict() for turn in turns], ensure_ascii=False, indent=2))
    elif args.command == "summary":
        from hobit_ax_agentos.services.session_state import SessionStateService

        session_id = args.session_id or settings.default_session_id
        summary = SessionStateService(str(settings.data_dir)).summary(session_id, limit=args.limit)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.command == "timeline":
        from hobit_ax_agentos.services.session_state import SessionStateService

        session_id = args.session_id or settings.default_session_id
        timeline = SessionStateService(str(settings.data_dir)).timeline(
            session_id,
            limit=args.limit,
        )
        print(json.dumps(timeline, ensure_ascii=False, indent=2))
    elif args.command == "export-session":
        from hobit_ax_agentos.services.maintenance import MaintenanceService

        session_id = args.session_id or settings.default_session_id
        service = MaintenanceService(settings.data_dir)
        if args.output:
            result = service.write_session_export(session_id, args.output, limit=args.limit)
        else:
            result = service.export_session(session_id, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "storage-stats":
        from hobit_ax_agentos.services.maintenance import MaintenanceService

        print(json.dumps(MaintenanceService(settings.data_dir).storage_stats(), ensure_ascii=False, indent=2))
    elif args.command == "storage-audit":
        from hobit_ax_agentos.services.storage_audit import StorageAuditService

        print(json.dumps(StorageAuditService(settings.data_dir).audit(), ensure_ascii=False, indent=2))
    elif args.command == "prune-storage":
        from hobit_ax_agentos.services.retention import RetentionService

        result = RetentionService(settings.data_dir).prune(
            older_than_days=args.older_than_days,
            dry_run=not args.apply,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "metrics":
        from hobit_ax_agentos.services.metrics import MetricsService

        print(json.dumps(MetricsService(settings.data_dir).summary(), ensure_ascii=False, indent=2))
    elif args.command == "alerts":
        from hobit_ax_agentos.services.alerts import AlertsService

        print(
            json.dumps(
                AlertsService(settings.data_dir).alerts(
                    running_minutes=args.running_minutes,
                    job_minutes=args.job_minutes,
                    delivery_minutes=args.delivery_minutes,
                    escalation_minutes=args.escalation_minutes,
                    deadline_days=args.deadline_days,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "agents":
        from hobit_ax_agentos.agentos.capabilities import agent_capabilities

        capabilities = agent_capabilities(settings)
        if args.enabled_only:
            capabilities = [capability for capability in capabilities if capability.enabled]
        print(json.dumps([capability.to_dict() for capability in capabilities], ensure_ascii=False, indent=2))
    elif args.command == "jobs":
        from hobit_ax_agentos.storage import AsyncJobStore

        jobs = AsyncJobStore(settings.data_dir).list_by_status(args.status, args.limit)
        print(json.dumps([job.to_dict() for job in jobs], ensure_ascii=False, indent=2))
    elif args.command == "job":
        from hobit_ax_agentos.storage import AsyncJobStore

        job = AsyncJobStore(settings.data_dir).get(args.job_id)
        print(json.dumps(job.to_dict() if job else None, ensure_ascii=False, indent=2))
    elif args.command == "run-job":
        from hobit_ax_agentos.services.async_job_worker import AsyncJobWorker

        result = AsyncJobWorker(settings=settings).run_one(
            args.job_id,
            timeout_seconds=args.timeout,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "run-jobs":
        from hobit_ax_agentos.services.async_job_worker import AsyncJobWorker

        worker = AsyncJobWorker(settings=settings)
        if args.watch:
            result = worker.run_loop(
                limit=args.limit,
                interval_seconds=args.interval_seconds,
                max_iterations=args.max_iterations,
                stop_when_idle=args.stop_when_idle,
                requeue_stale_minutes=args.requeue_stale_minutes,
            )
        else:
            result = worker.run_queued(limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "requeue-stale-jobs":
        from hobit_ax_agentos.services.async_job_worker import AsyncJobWorker

        result = AsyncJobWorker(settings=settings).requeue_stale_running(
            older_than_minutes=args.older_than_minutes,
            limit=args.limit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "retry-job":
        from hobit_ax_agentos.services.async_job_worker import AsyncJobWorker
        from hobit_ax_agentos.storage import AsyncJobStore

        store = AsyncJobStore(settings.data_dir)
        source = store.get(args.job_id)
        if source is None:
            print(json.dumps(None, ensure_ascii=False, indent=2))
            return
        if source.status not in {"FAILED", "CANCELLED"}:
            raise SystemExit(f"job {args.job_id} is not retryable from state {source.status}")
        retry = store.create_retry(source)
        result = AsyncJobWorker(settings=settings, job_store=store).run_one(
            retry.job_id,
            timeout_seconds=args.timeout,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "cancel-job":
        from hobit_ax_agentos.storage import AsyncJobStore

        job = AsyncJobStore(settings.data_dir).cancel(args.job_id, reason=args.reason)
        print(json.dumps(job.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "outbox":
        from hobit_ax_agentos.storage import OutboxStore

        store = OutboxStore(settings.data_dir)
        if args.session_id:
            deliveries = store.list_by_session(args.session_id, limit=args.limit)
            if args.status:
                deliveries = [
                    delivery for delivery in deliveries if delivery.status == args.status.upper()
                ]
        else:
            deliveries = store.list_by_status(status=args.status, limit=args.limit)
        print(json.dumps([delivery.to_dict() for delivery in deliveries], ensure_ascii=False, indent=2))
    elif args.command == "mark-delivery-sent":
        from hobit_ax_agentos.storage import OutboxStore

        delivery = OutboxStore(settings.data_dir).mark_sent(args.delivery_id)
        print(json.dumps(delivery.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "mark-delivery-failed":
        from hobit_ax_agentos.storage import OutboxStore

        delivery = OutboxStore(settings.data_dir).mark_failed(args.delivery_id, error=args.error)
        print(json.dumps(delivery.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "dispatch-delivery":
        from hobit_ax_agentos.services.delivery_dispatcher import DeliveryDispatcher

        result = DeliveryDispatcher(settings).dispatch_one(args.delivery_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "render-delivery":
        from hobit_ax_agentos.services.delivery_renderer import DeliveryRenderer
        from hobit_ax_agentos.storage import OutboxStore

        result = DeliveryRenderer(outbox_store=OutboxStore(settings.data_dir)).render_one(
            args.delivery_id,
            channel=args.channel,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "dispatch-outbox":
        from hobit_ax_agentos.services.delivery_dispatcher import DeliveryDispatcher

        result = DeliveryDispatcher(settings).dispatch_pending(limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "plans":
        from hobit_ax_agentos.storage import CoordinationPlanStore

        session_id = args.session_id or settings.default_session_id
        plans = CoordinationPlanStore(settings.data_dir).list_by_session(session_id, args.limit)
        print(json.dumps([plan.to_dict() for plan in plans], ensure_ascii=False, indent=2))
    elif args.command == "runs":
        from hobit_ax_agentos.storage import RunStore

        store = RunStore(settings.data_dir)
        if args.all:
            runs = store.list_by_state(args.state, args.limit)
        else:
            session_id = args.session_id or settings.default_session_id
            runs = store.list_by_session(session_id, args.limit, state=args.state)
        print(json.dumps([run.to_dict() for run in runs], ensure_ascii=False, indent=2))
    elif args.command == "run":
        from hobit_ax_agentos.storage import RunStore

        run = RunStore(settings.data_dir).get(args.run_id)
        print(json.dumps(run.to_dict() if run else None, ensure_ascii=False, indent=2))
    elif args.command == "run-trace":
        from hobit_ax_agentos.services.run_trace import RunTraceService

        trace = RunTraceService(settings.data_dir).trace(
            args.run_id,
            conversation_limit=args.conversation_limit,
        )
        print(json.dumps(trace, ensure_ascii=False, indent=2))
    elif args.command == "retry-run":
        from hobit_ax_agentos.services.run_retry import RunRetryService

        result = RunRetryService(settings).retry(args.run_id, timeout_seconds=args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "cancel-run":
        from hobit_ax_agentos.services.run_control import RunControlService

        result = RunControlService(settings.data_dir).cancel(args.run_id, reason=args.reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "escalations":
        from hobit_ax_agentos.storage import EscalationStore

        cases = EscalationStore(settings.data_dir).list_all()
        if args.status:
            cases = [case for case in cases if case.status == args.status.upper()]
        print(json.dumps([case.to_dict() for case in cases], ensure_ascii=False, indent=2))
    elif args.command == "ack-escalation":
        from hobit_ax_agentos.storage import EscalationStore

        case = EscalationStore(settings.data_dir).acknowledge(args.escalation_id)
        print(json.dumps(case.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "assign-escalation":
        from hobit_ax_agentos.storage import EscalationStore

        case = EscalationStore(settings.data_dir).assign(args.escalation_id, args.assignee)
        print(json.dumps(case.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "note-escalation":
        from hobit_ax_agentos.storage import EscalationStore

        case = EscalationStore(settings.data_dir).add_note(
            args.escalation_id,
            author=args.author,
            text=args.text,
            visibility=args.visibility,
        )
        print(json.dumps(case.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "resolve-escalation":
        from hobit_ax_agentos.agents.escalation import EscalationAgent

        case = EscalationAgent(settings).resolve(
            args.escalation_id, signal=args.signal, comment=args.comment
        )
        print(json.dumps(case.to_dict(), ensure_ascii=False, indent=2))


def _service_result_to_dict(result) -> dict:
    return {
        "run_id": result.run_id,
        "trace_id": result.trace_id,
        "final": result.final,
        "run_summary": result.run_summary,
        "worker_results": result.worker_results,
    }


def _parse_field_value(raw: str) -> object:
    """Parse a --field KEY=VALUE value as JSON when possible, else keep it as a string."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _load_payload(payload: str | None, payload_file: str | None) -> dict:
    if payload and payload_file:
        raise SystemExit("Use either --payload or --payload-file, not both.")
    if payload_file:
        try:
            return json.loads(Path(payload_file).read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in --payload-file: {exc}") from exc
    if payload:
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in --payload: {exc}") from exc
    raise SystemExit("Provide --payload or --payload-file.")


if __name__ == "__main__":
    main()
