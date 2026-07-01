# hobit-ax-agentos

`hobit-ax-agentos`는 기존 `hobit-ax/regulation_rag`를 AgentOS 위에서 실행하기 위한 Hobit AX 서비스 레포입니다.

AgentOS는 범용 실행 계층으로 유지하고, 이 레포는 Hobit AX에 특화된 채널 정규화, 지식 질의, persona context, trigger, escalation, 최종 응답 조립, delivery tracking을 담당합니다.

## 현재 구현 범위

- `ChannelGateway`: API, web, portal, KakaoTalk, generic payload를 공통 `IncomingMessage`로 정규화합니다.
- `CoordinatorAgent`: 메시지를 분류하고 AgentOS `TaskGraphIR` 및 `CoordinationPlan`을 생성합니다. 사전 분류는 `routing_reasons.preliminary_classification`에, `knowledge_query` 실행 후 실제 LLM 분류 결과는 `routing_reasons.actual_classification`에 별도로 기록됩니다.
- `RegulationRagAdapter`: `regulation_rag.workers.supervisor.Supervisor`/`QueryCache`/`EvalCache`/`TraceStore`를 프로세스당 한 번만 구성해 재사용하고, `ProfileStore`에 저장된 `UserProfile`을 주입해 규정 평가(`condition_checks`, `lex_superior`)가 실제로 수행되도록 합니다. 매 질의마다 regulation_rag `QueryTrace`를 기록해 self-strengthening feedback loop의 진입점을 제공합니다.
- `KnowledgeAgent`: 위 adapter를 감싸 structured state(+ `regulation_rag_trace_id`)를 반환합니다.
- `ProfileStore`: regulation_rag `UserProfile.from_dict()`와 동일한 모양의 프로필을 `data/user_profiles.jsonl`에 저장합니다. `ServiceRunner`가 매 메시지마다 `user_id` 기준으로 자동 조회해 주입합니다.
- `PersonaWorker` / `PersonaStore`: deterministic persona context를 만들고 `data/persona_snapshots.jsonl`에 저장합니다. 매 메시지마다 동기 호출되는 LLM-free 경로입니다.
- `PersonaPrefetchService`: 저장된 프로필이 있으면 regulation_rag `workers.persona_worker`(LLM 기반 `predict_questions` + `prefetch_background`)를 그대로 호출해 예측 질문을 만들고 QueryCache를 미리 워밍합니다. `/persona/prefetch`와 `persona-prefetch` CLI가 사용하는 온디맨드 경로입니다.
- `TriggerAgent` / `DeadlineWatchStore`: deadline watch와 due trigger event를 관리합니다. `regulation_change_events()`는 `RegulationRagAdapter.reconcile_regulations()`(manifest hash diff)로 감지한 규정 변경을 영향받은 `issue_type`을 watch 중인 사용자에게 알립니다.
- `EscalationAgent` / `EscalationStore`: human review case를 저장하고 acknowledge/resolve 상태 전환을 지원합니다. resolve 시 `signal`(positive/negative/neutral)을 regulation_rag `TraceStore.add_feedback()`으로 전달해 self-strengthening feedback loop를 다시 연결합니다.
- `ConversationStore`: 사용자/assistant turn을 `data/conversation_turns.jsonl`에 저장합니다.
- `CoordinationPlanStore`: 라우팅 계획을 `data/coordination_plans.jsonl`에 저장합니다.
- `RunStore`: AgentOS run summary와 worker 결과를 `data/agent_runs.jsonl`에 저장합니다.
- `AsyncJobStore`: 비동기 submit 요청과 run 결과 연결 상태를 `data/async_jobs.jsonl`에 저장합니다.
- `Agent contract validation`: 각 worker 결과를 capability `output_schema` 기준으로 검증하고, 위반 시 run을 `FAILED`로 기록합니다.
- `Plan execution validation`: Coordinator가 만든 plan 밖의 node/agent lease를 거부하고, 실제 실행 sequence를 run summary에 기록합니다.
- `OutboxStore`: 최종 응답 delivery를 `data/outbox.jsonl`에 저장하고 `PENDING/SENT/FAILED` 상태를 추적합니다.
- `DeliveryRenderer`: outbox delivery를 API/web/portal/KakaoTalk/generic 채널 payload로 렌더링합니다.
- `DeliveryDispatcher`: pending delivery를 transport로 보내고 성공/실패 상태를 반영합니다.
- `SessionStateService`: 세션 summary를 한 번에 조회합니다.
- `MaintenanceService`: 세션 export와 JSONL storage stats를 제공합니다.
- `DoctorService`: AgentOS/Hobit AX/regulation_rag 로컬 의존성과 storage readiness를 진단합니다.

`ActionAgent`는 Contract Studio 통합 트랙으로 분리되어 있으며 기본 graph에서는 제외됩니다. 기존 stub을 실험적으로 포함하려면 다음 환경 변수를 켭니다.

```powershell
$env:HOBIT_ENABLE_ACTION_AGENT="true"
```

## 멀티에이전트 협업 구조

에이전트별 병렬 개발을 위해 루트 `agents/` 아래에 독립 작업 폴더를 둡니다.
각 담당자는 자기 에이전트 폴더의 `agent.toml`, `contract.md`, `template.py`,
`tests/test_contract_template.py`를 기준으로 작업하고, 공통 graph/schema 변경이 필요한
경우에만 `src/hobit_ax_agentos` 런타임 코드를 함께 수정합니다.

- 전체 가이드: `docs/multi-agent-development.md`
- 폴더 목록과 규칙: `agents/README.md`
- 새 에이전트 추가 템플릿: `agents/_template/`

현재 정의된 협업 폴더는 `agent_hobit_channel_gateway`, `hobit_coordinator`,
`agent_hobit_persona`, `agent_hobit_trigger`, `agent_hobit_knowledge`,
`agent_hobit_action`, `agent_hobit_escalation`, `agent_hobit_final`입니다.

## 로컬 실행

AgentOS 커널을 먼저 실행합니다.

```powershell
cd C:\Users\SEONGMIN\Documents\Workspace\Projects\agent-os
cargo run --manifest-path rust\kernel\Cargo.toml
```

별도 터미널에서 Hobit AX AgentOS 서비스를 실행합니다.

```powershell
cd C:\Users\SEONGMIN\Documents\Workspace\Projects\hobit-ax-agentos
python -m pip install -e .[dev]
$env:AGENTOS_REPO_PATH="C:\Users\SEONGMIN\Documents\Workspace\Projects\agent-os"
$env:HOBIT_AX_REPO_PATH="C:\Users\SEONGMIN\Documents\Workspace\Projects\hobit-ax"
python -m hobit_ax_agentos.cli query "복수전공 신청 기간 알려줘"
```

설치 없이 바로 확인하려면 `PYTHONPATH`를 지정합니다.

```powershell
$env:PYTHONPATH="src"
python -m hobit_ax_agentos.cli query "복수전공 신청 기간 알려줘" --dry-run
```

로컬 의존성 상태는 다음 명령으로 확인합니다.

```powershell
python -m hobit_ax_agentos.cli doctor
```

## CLI

```powershell
python -m hobit_ax_agentos.cli doctor
python -m hobit_ax_agentos.cli integration-probe
python -m hobit_ax_agentos.cli smoke-e2e --render-channel web
python -m hobit_ax_agentos.cli config
python -m hobit_ax_agentos.cli query "복수전공 신청 기간 알려줘" --dry-run
python -m hobit_ax_agentos.cli gateway web --payload '{"message":"복수전공 신청 기간 알려줘","member_id":"u1"}' --dry-run
python -m hobit_ax_agentos.cli gateway web --payload-file .\payload.json --dry-run
python -m hobit_ax_agentos.cli profile-set u1 --type student --field grade=3 --field scope=undergraduate --field status=enrolled --field gpa=3.5 --field credits_earned=80 --field major=컴퓨터학과
python -m hobit_ax_agentos.cli profile-get u1
python -m hobit_ax_agentos.cli persona "복수전공 신청 준비해야 해" --save
python -m hobit_ax_agentos.cli persona-prefetch "복수전공 신청 준비해야 해" --user-id u1 --session-id local-session
python -m hobit_ax_agentos.cli personas --session-id local-session
python -m hobit_ax_agentos.cli deadline-trigger academic.plural_major 2026-07-05 --today 2026-07-01
python -m hobit_ax_agentos.cli watch-deadline academic.plural_major 2026-07-05 --window-days 7
python -m hobit_ax_agentos.cli deadline-watches --session-id local-session
python -m hobit_ax_agentos.cli due-deadline-triggers --today 2026-07-01
python -m hobit_ax_agentos.cli due-deadline-triggers --today 2026-07-01 --dispatch
python -m hobit_ax_agentos.cli regulation-refresh
python -m hobit_ax_agentos.cli regulation-refresh --dispatch
python -m hobit_ax_agentos.cli sessions
python -m hobit_ax_agentos.cli history --session-id local-session
python -m hobit_ax_agentos.cli summary --session-id local-session
python -m hobit_ax_agentos.cli timeline --session-id local-session
python -m hobit_ax_agentos.cli export-session --session-id local-session
python -m hobit_ax_agentos.cli export-session --session-id local-session --output data/exports/local-session.json
python -m hobit_ax_agentos.cli storage-stats
python -m hobit_ax_agentos.cli storage-audit
python -m hobit_ax_agentos.cli prune-storage --older-than-days 30
python -m hobit_ax_agentos.cli prune-storage --older-than-days 30 --apply
python -m hobit_ax_agentos.cli metrics
python -m hobit_ax_agentos.cli alerts
python -m hobit_ax_agentos.cli alerts --job-minutes 5
python -m hobit_ax_agentos.cli agents
python -m hobit_ax_agentos.cli agents --enabled-only
python -m hobit_ax_agentos.cli jobs --status COMPLETED
python -m hobit_ax_agentos.cli job <job_id>
python -m hobit_ax_agentos.cli run-job <job_id>
python -m hobit_ax_agentos.cli run-jobs --limit 10
python -m hobit_ax_agentos.cli run-jobs --watch --interval-seconds 1
python -m hobit_ax_agentos.cli requeue-stale-jobs --older-than-minutes 30
python -m hobit_ax_agentos.cli retry-job <job_id>
python -m hobit_ax_agentos.cli cancel-job <job_id> --reason "duplicate request"
python -m hobit_ax_agentos.cli outbox --session-id local-session
python -m hobit_ax_agentos.cli dispatch-outbox --limit 20
python -m hobit_ax_agentos.cli dispatch-delivery <delivery_id>
python -m hobit_ax_agentos.cli render-delivery <delivery_id> --channel kakao
python -m hobit_ax_agentos.cli mark-delivery-sent <delivery_id>
python -m hobit_ax_agentos.cli mark-delivery-failed <delivery_id> --error "transport error"
python -m hobit_ax_agentos.cli plans --session-id local-session
python -m hobit_ax_agentos.cli runs --session-id local-session
python -m hobit_ax_agentos.cli runs --all --state FAILED
python -m hobit_ax_agentos.cli run <run_id>
python -m hobit_ax_agentos.cli run-trace <run_id>
python -m hobit_ax_agentos.cli retry-run <run_id>
python -m hobit_ax_agentos.cli cancel-run <run_id> --reason "operator stop"
python -m hobit_ax_agentos.cli escalations
python -m hobit_ax_agentos.cli ack-escalation <escalation_id>
python -m hobit_ax_agentos.cli assign-escalation <escalation_id> reviewer_1
python -m hobit_ax_agentos.cli note-escalation <escalation_id> "검토 메모"
python -m hobit_ax_agentos.cli resolve-escalation <escalation_id> --signal positive --comment "checked, correct"
```

## API

```powershell
uvicorn hobit_ax_agentos.api.main:app --reload
```

`AGENTOS_API_TOKEN`이 설정되어 있으면 `/health`, `/ready`를 제외한 endpoint는 `Authorization: Bearer <token>` 또는 `x-api-token: <token>` 헤더가 필요합니다. 로컬 개발처럼 token이 설정되지 않은 경우에는 인증을 요구하지 않습니다.

`HOBIT_RATE_LIMIT_PER_MINUTE`를 1 이상의 값으로 설정하면 `/health`, `/ready`를 제외한 endpoint에 1분 단위 in-memory rate limit이 적용됩니다. 기본값 `0`은 비활성입니다.

주요 endpoint:

- `GET /health`
- `GET /ready`
- `GET /doctor`
- `GET /integration/probe`
- `POST /smoke/e2e`
- `GET /config`
- `POST /query`
- `POST /query/submit`
- `POST /gateway/{channel}`
- `POST /gateway/{channel}/dry-run`
- `POST /gateway/{channel}/query`
- `POST /gateway/{channel}/submit`
- `PUT /profiles/{user_id}`
- `GET /profiles/{user_id}`
- `POST /persona/prefetch`
- `GET /jobs`
- `GET /jobs?status=QUEUED|RUNNING|COMPLETED|FAILED|CANCELLED`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/run`
- `POST /jobs/run-queued`
- `POST /jobs/requeue-stale`
- `POST /jobs/{job_id}/retry`
- `POST /jobs/{job_id}/cancel`
- `GET /sessions`
- `GET /sessions/{session_id}/persona`
- `GET /sessions/{session_id}/personas`
- `GET /sessions/{session_id}/history`
- `GET /sessions/{session_id}/summary`
- `GET /sessions/{session_id}/timeline`
- `GET /sessions/{session_id}/export`
- `GET /maintenance/storage`
- `GET /maintenance/audit`
- `POST /maintenance/prune`
- `GET /metrics/summary`
- `GET /alerts`
- `GET /agents`
- `GET /agents?include_disabled=false`
- `GET /outbox`
- `GET /outbox?status=PENDING|SENT|FAILED`
- `GET /sessions/{session_id}/outbox`
- `POST /outbox/{delivery_id}/sent`
- `POST /outbox/{delivery_id}/failed`
- `POST /outbox/{delivery_id}/dispatch`
- `GET /outbox/{delivery_id}/render`
- `GET /outbox/{delivery_id}/render?channel=api|web|portal|kakao|kakaotalk`
- `POST /outbox/dispatch`
- `GET /sessions/{session_id}/plans`
- `GET /sessions/{session_id}/runs`
- `GET /sessions/{session_id}/runs?state=RUNNING|FAILED|TIMED_OUT|COMPLETED`
- `GET /runs`
- `GET /runs?state=RUNNING|FAILED|TIMED_OUT|COMPLETED`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/trace`
- `POST /runs/{run_id}/retry`
- `POST /runs/{run_id}/cancel`
- `POST /triggers/deadline-watches`
- `GET /sessions/{session_id}/deadline-watches`
- `POST /triggers/deadline-watches/due`
- `POST /triggers/regulation-refresh`
- `GET /escalations`
- `GET /escalations?status=OPEN|ACKNOWLEDGED|RESOLVED`
- `GET /escalations/{escalation_id}`
- `POST /escalations/{escalation_id}/acknowledge`
- `POST /escalations/{escalation_id}/assign`
- `POST /escalations/{escalation_id}/notes`
- `POST /escalations/{escalation_id}/resolve`
- `POST /triggers/deadline-check`

`/triggers/deadline-watches/due`는 기본적으로 due event만 반환합니다. `{"dispatch": true}`를 함께 보내면 생성된 trigger message를 `ServiceRunner`로 넘겨 AgentOS run을 생성합니다.

`/triggers/regulation-refresh`는 `configs/regulation_manifest.yaml`과 ingested 상태를 비교(hash diff)해 변경된 규정을 감지하고, 영향받은 `issue_type`에 대해 `ACTIVE` deadline watch를 가진 사용자에게 `regulation_changed` trigger event를 발행합니다. `{"dispatch": true}`를 보내면 `due-deadline-triggers`와 동일하게 `ServiceRunner`로 바로 실행합니다. 시스템 전체 사용자 타임라인을 순회하는 범위는 agentos에 타임라인 저장소가 아직 없어 포함하지 않습니다 — watch를 등록한 사용자로 범위가 한정됩니다.

`PUT /profiles/{user_id}`는 regulation_rag `UserProfile.from_dict()`와 동일한 모양(`profile_type` + `profile` 필드 dict)으로 프로필을 저장합니다. `ServiceRunner.run_message()`는 메시지에 `metadata.profile`이 없으면 이 저장소에서 `user_id` 기준으로 자동 조회해 채웁니다 — 명시적으로 `metadata.profile`을 실어 보낸 호출은 그대로 우선합니다. 저장된 프로필이 없으면 `Supervisor`는 `user_profile=None`으로 동작하며, 이 경우 규정 평가(`regulation_evaluate`) 단계가 스킵되고 `cited_rule_ids`가 항상 비게 됩니다.

`/integration/probe`와 `integration-probe` CLI는 실제 AgentOS kernel `/health`, `regulation_rag` import, Supervisor build, 샘플 RAG query를 점검합니다. 외부 의존성이 꺼져 있거나 데이터가 부족하면 `degraded`로 표시하되 서비스 자체는 중단하지 않습니다.

`/smoke/e2e`와 `smoke-e2e` CLI는 graph preview, `ServiceRunner` 실행, run record 저장, outbox 생성, delivery render까지 백엔드 경로를 한 번에 검증합니다. 실제 AgentOS kernel과 `regulation_rag`가 준비되지 않은 경우 실패 단계가 `steps`에 표시됩니다.

`/gateway/{channel}/dry-run`은 channel payload를 정규화한 뒤 graph preview를 반환합니다. `/gateway/{channel}/query`는 같은 정규화 과정을 거친 메시지를 실제 `ServiceRunner`로 실행합니다.

`/query/submit`과 `/gateway/{channel}/submit`은 HTTP 요청을 오래 붙잡지 않고 async job을 만든 뒤 `job_id`와 `status_url`을 반환합니다. 백그라운드 실행 결과는 `/jobs/{job_id}`에서 `QUEUED/RUNNING/COMPLETED/FAILED/CANCELLED` 상태와 실제 `run_id`, `trace_id`, `result`, `error`로 확인합니다. `FAILED` 또는 `CANCELLED` job은 `/jobs/{job_id}/retry`로 원본 메시지와 timeout을 복원해 새 job으로 재실행할 수 있고, 아직 `QUEUED`인 job은 `/jobs/{job_id}/cancel`로 취소할 수 있습니다.

`/jobs/{job_id}/run`, `/jobs/run-queued`, `run-job`, `run-jobs`는 저장된 `QUEUED` job을 별도 worker 프로세스에서 실행하기 위한 경로입니다. FastAPI background task에만 의존하지 않고 durable JSONL queue를 기준으로 재개할 수 있습니다.

`run-jobs --watch`는 worker loop로 동작하며 새 `QUEUED` job을 계속 polling합니다. 개발/단일 머신 운영에서는 별도 터미널에서 `python -m hobit_ax_agentos.cli run-jobs --watch --interval-seconds 1` 형태로 실행할 수 있습니다.

`requeue-stale-jobs`, `/jobs/requeue-stale`, `run-jobs --watch --requeue-stale-minutes 30`은 worker crash 등으로 오래 `RUNNING`에 남은 async job을 다시 `QUEUED`로 되돌립니다.

Async job은 `/sessions`, `/sessions/{session_id}/summary`, `/sessions/{session_id}/timeline`, `/sessions/{session_id}/export`에도 포함되어 세션 단위 운영 흐름에서 submit 상태와 run 연결을 함께 추적할 수 있습니다.

`AsyncJobStore`, `RunStore`, `OutboxStore`의 JSONL write 경로는 lock file을 사용해 단일 머신 멀티프로세스 write 충돌을 줄입니다. 여러 서버 인스턴스나 네트워크 파일시스템 운영은 향후 DB/queue backend로 전환하는 것이 안전합니다.

`/query` 또는 `/gateway/{channel}/query` 입력에 `metadata.idempotency_key` 또는 top-level `idempotency_key`를 넣으면 같은 key의 중복 요청은 기존 run 결과를 재사용합니다. 이때 새 conversation turn, run, outbox delivery를 만들지 않습니다.

`/runs/{run_id}/retry`와 `retry-run`은 `FAILED`, `TIMED_OUT`, `BLOCKED`, `CANCELLED` 상태의 run만 재실행합니다. 원본 메시지는 같은 session에서 해당 run 생성 시각 이전의 마지막 USER turn으로 복원하고, 새 메시지 metadata에 `retry.retry_of_run_id`와 `retry.source_turn_id`를 남깁니다.

`/runs/{run_id}/cancel`과 `cancel-run`은 `PENDING`, `RUNNING`, `BLOCKED` run을 앱 레벨에서 `CANCELLED`로 닫습니다. 연결된 pending delivery는 `FAILED`로, 연결된 open escalation은 `RESOLVED`로 정리합니다.

`/outbox/{delivery_id}/render`와 `render-delivery` CLI는 저장된 delivery를 실제 채널 응답 payload로 렌더링합니다. KakaoTalk은 skill response `version/template` 형식으로, web/portal은 `agent_response` event 형식으로 반환합니다.

`/alerts`와 `alerts` CLI는 오래 진행 중인 async job/run, 실패한 async job, 오래 pending 상태인 delivery, 오래 open 상태인 escalation, 마감 임박 deadline watch를 운영 alert로 집계합니다. threshold는 query parameter 또는 CLI option으로 조정할 수 있습니다.

`/maintenance/audit`와 `storage-audit` CLI는 JSONL record 파싱, dataclass schema 로딩, run-plan/outbox-run/escalation-run/idempotency-run 참조 무결성을 점검합니다.

`/maintenance/prune`과 `prune-storage` CLI는 오래된 JSONL record를 보존 기간 기준으로 정리합니다. CLI는 `--apply`를 붙이지 않으면 dry-run만 수행합니다.

`/persona/prefetch`와 `persona-prefetch` CLI는 `agents/persona.py`의 deterministic 경로(`/query` 매 호출 시 동기 실행)와 별개로, 저장된 프로필이 있으면 regulation_rag `workers/persona_worker.py`를 그대로 호출해 LLM 예측 질문(`predicted_questions`)을 만들고 `prefetch_background()`로 `QueryCache`를 미리 워밍합니다. 저장된 프로필이 없거나 LLM 호출이 실패하면 deterministic 스냅샷으로 자동 폴백합니다. 결과의 `prefetch_result`에 `triggered/succeeded/failed/questions`가 기록됩니다.

`/escalations/{escalation_id}/resolve`는 body로 `{"signal": "positive"|"negative"|"neutral", "comment": "..."}`을 받습니다. 케이스가 `regulation_rag_trace_id`를 갖고 있으면(즉 `KnowledgeAgent` 경로로 생성된 케이스라면) 이 signal을 regulation_rag `TraceStore.add_feedback()`으로 전달해 `TraceAnalyzer`의 issue_type/cited_rule 성공률 집계에 사람 검토 결과가 반영되도록 합니다. trace를 찾지 못하거나 전달이 실패해도 escalation resolve 자체는 항상 성공합니다.

하이브리드(dense+sparse) 검색은 `OPENAI_API_KEY`가 설정되어 있고 Qdrant 백엔드(둘 중 하나)가 준비된 경우에만 활성화됩니다 — regulation_rag `api/main.py`와 동일한 우선순위로, `HOBIT_QDRANT_URL`이 설정돼 있으면 원격 서버를, 아니면 로컬 파일모드(`HOBIT_QDRANT_PATH`, 기본값 `regulation_rag/data/qdrant_store`)를 사용합니다. `HOBIT_QDRANT_COLLECTION`(기본 `hobit_ax_content`)으로 컬렉션명을 지정합니다. `qdrant-client`/`kiwipiepy`/`openai` 패키지나 연결이 준비되지 않으면 경고만 남기고 자동으로 sparse-only 검색으로 폴백합니다. `config.py`는 `hobit-ax/.env`를 모듈 로드 시점에 직접 읽어들이므로(`regulation_rag/workers/_llm.py`가 LLM 호출 시점에야 지연 로드하는 것보다 먼저), `.env`에만 있고 셸 환경변수로는 없는 `OPENAI_API_KEY`/`UPSTAGE_API_KEY`도 `AppSettings` 생성 시점에 인식됩니다.

`/config`와 `config` CLI는 runtime 설정을 보여주되 API token 값은 노출하지 않고 설정 여부만 표시합니다.

## 검증

```powershell
python -m compileall -q .\src .\tests
pytest -q
```

테스트는 실제 AgentOS 커널 없이도 `ServiceRunner`의 주요 실행 경로를 검증할 수 있도록 fake kernel client를 사용합니다. 현재 검증 범위는 정상 지식 응답 branch, human-review escalation branch, agent output contract validation, contract violation 실패 기록, plan execution validation, rogue lease 실패 기록, escalation assign/note workflow, worker 실패/timeout run trace, retry run 복원, run cancel 정리, async job submit/result/error 조회, async job worker 실행/실패/skip/batch/loop/stale requeue 처리, async job 세션 summary/timeline/directory 반영, JSONL file lock 기반 동시 write 보존, idempotent run reuse, API token/rate limit 보호, integration probe, E2E smoke report, operational alerts, storage audit/prune, sanitized config snapshot, session directory, persona snapshot 저장, conversation 저장, delivery outbox 저장/dispatch/render, coordination plan 저장(사전/실제 classification), run trace 저장/조회, session timeline, capability manifest, deadline watch 발행, regulation 변경 감지 trigger event, session export, storage stats, metrics summary, doctor/readiness 진단, gateway intake, API 운영 endpoint입니다.

regulation_rag 연동(UserProfile 주입에 따른 `cited_rule_ids` 채움, escalation resolve → `TraceStore.add_feedback` 전달, LLM 기반 persona prefetch + QueryCache 워밍)은 실제 LLM/데이터를 사용하는 수동 검증으로 확인했습니다 — `profile-set`으로 프로필을 채운 뒤 `query`/`integration-probe`로 before/after `cited_rule_ids`를 비교하고, `persona-prefetch`로 예측 질문과 `prefetch_result`를 확인하세요.
