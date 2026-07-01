# Hobit AX Multi-Agent Collaboration Manual

이 문서는 여러 명이 Hobit AX 멀티에이전트 시스템을 동시에 개발할 때 따르는
실무 매뉴얼입니다. 핵심 원칙은 간단합니다.

각 담당자는 기본적으로 `agents/<agent_id>/` 폴더만 수정합니다. 공통 계약,
AgentOS graph, runtime schema, API, frontend에 영향을 주는 변경은 별도 절차를
거쳐 공유 영역으로 승격합니다.

## 1. 전체 구조

```text
hobit-ax-agentos/
  agents/                         # 협업용 에이전트 작업 공간
    agent_hobit_knowledge/
      agent.toml                  # 에이전트 메타데이터와 AgentOS 연결 정보
      contract.md                 # 입력/출력/불변조건/핸드오프 계약
      template.py                 # 담당자가 구현을 시작하는 템플릿
      tests/test_contract_template.py
      README.md
    ...

  src/hobit_ax_agentos/agents/     # 실제 서비스가 import하는 런타임 코드
  src/hobit_ax_agentos/agentos/    # graph/capability/runner 등 AgentOS 연결 코드
  src/hobit_ax_agentos/schemas.py  # 런타임 output schema
  tests/                           # 통합/회귀 테스트
```

`agents/`와 `src/hobit_ax_agentos/agents/`는 목적이 다릅니다.

| 위치 | 용도 | 누가 수정하나 |
| --- | --- | --- |
| `agents/<agent_id>/` | 에이전트별 협업, 계약, 템플릿, 로컬 테스트 | 각 에이전트 담당자 |
| `src/hobit_ax_agentos/agents/` | 실제 런타임 구현 | 통합 담당자 또는 승격 단계의 에이전트 담당자 |
| `src/hobit_ax_agentos/agentos/` | AgentOS graph/capability/plan validation | 오케스트레이션 담당자 |
| `src/hobit_ax_agentos/schemas.py` | 공유 output schema | 계약 변경 승인 후 수정 |

## 2. 에이전트 카테고리

Hobit AX 에이전트는 크게 네 계층으로 나눕니다.

| 카테고리 | 에이전트 | 역할 |
| --- | --- | --- |
| Intake / Trigger | `agent_hobit_channel_gateway`, `agent_hobit_trigger` | 외부 입력 또는 선제 이벤트를 `IncomingMessage` 흐름으로 진입시킴 |
| Planning / Context | `hobit_coordinator`, `agent_hobit_persona` | 실행 계획, routing reason, 사용자/세션 맥락 생성 |
| Domain Execution | `agent_hobit_knowledge`, `agent_hobit_action`, `agent_hobit_escalation` | 규정 질의, 행정 처리안, human review 패키징 |
| Response / Delivery | `agent_hobit_final` | 최종 응답과 delivery payload 생성 |

## 3. 역할과 책임

### 에이전트 담당자

- 자기 폴더의 `contract.md`를 먼저 읽고 구현 범위를 확인합니다.
- `template.py`를 기준으로 입력/출력 형태를 맞춥니다.
- 자기 폴더의 `tests/test_contract_template.py`를 확장합니다.
- 다른 에이전트가 의존하는 output field를 변경할 때는 계약 변경 절차를 따릅니다.

### 오케스트레이션 담당자

- `hobit_coordinator`와 `src/hobit_ax_agentos/agentos/graph_builder.py`를 관리합니다.
- 어떤 에이전트가 graph node로 들어가는지, 어떤 조건으로 branch되는지 결정합니다.
- `CoordinationPlan`과 실제 실행 결과가 맞는지 검증합니다.

### 계약/schema 담당자

- `contract.md`와 `src/hobit_ax_agentos/schemas.py`의 일관성을 확인합니다.
- `agent.toml`의 `output_schema`가 실제 schema를 가리키는지 확인합니다.
- 계약 변경 시 downstream 에이전트 영향도를 확인합니다.

### 통합 담당자

- `agents/<agent_id>/template.py`에서 안정화된 구현을 런타임 코드로 옮깁니다.
- `ServiceRunner`, API, CLI, frontend와의 연결을 확인합니다.
- 전체 테스트와 smoke test를 실행합니다.

## 4. 에이전트 폴더 파일 규칙

모든 에이전트 폴더는 다음 파일을 유지해야 합니다.

### `agent.toml`

머신이 읽는 manifest입니다. 테스트가 이 파일을 읽어 폴더 완성도를 검증합니다.

필수 섹션:

- `[agent]`: `id`, `display_name`, `runtime_module`, `runtime_class`, `status`, `owner`
- `[agentos]`: `node_id`, `capability_id`, `executor_kind`, `graph_role`
- `[contract]`: `input_contract`, `output_contract`, `output_schema`
- `[handoff]`: `upstream`, `downstream`, `shared_state`
- `[development]`: `editable_scope`, `template_entrypoint`, `test_template`

수정 원칙:

- `id`는 폴더명과 일치시키는 것을 기본으로 합니다.
- AgentOS graph node로 실행되는 에이전트는 runtime capability와 `agent.id`가 일치해야 합니다.
- `editable_scope`는 자기 폴더만 가리켜야 합니다.

### `contract.md`

사람이 읽는 계약 문서입니다. downstream 담당자가 구현 코드를 보지 않고도 의존할 수 있어야 합니다.

반드시 포함할 내용:

- Input: 어떤 payload key를 받는가
- Output: 어떤 field를 반환하는가
- Invariants: 절대 깨면 안 되는 규칙
- Handoff: 다음 에이전트가 무엇을 믿어도 되는가

좋은 계약 예시:

```markdown
## Output

- answer: 사용자에게 보여줄 수 있는 한국어 답변 문자열
- confidence: 0.0 이상 1.0 이하 숫자
- requires_action: Action Agent 실행 여부
- requires_human_review: Escalation Agent 실행 여부
```

나쁜 계약 예시:

```markdown
적당히 답변과 필요한 정보를 반환한다.
```

### `template.py`

각 담당자의 시작점입니다. 처음에는 간단한 skeleton이어도 되지만 다음 조건을 지켜야 합니다.

- JSON 직렬화 가능한 `dict`를 반환합니다.
- 외부 API 호출은 작은 adapter 함수 뒤로 감춥니다.
- 입력 payload를 in-place로 변경하지 않습니다.
- 계약상 required field는 항상 반환합니다.

### `tests/test_contract_template.py`

최소한 다음을 검증해야 합니다.

- required output field가 존재하는가
- branch flag가 의도대로 계산되는가
- high-risk 또는 missing-data 같은 주요 edge case가 깨지지 않는가

## 5. 일반 작업 절차

### 5.1 자기 에이전트만 수정하는 경우

1. 담당 폴더로 이동합니다.

```powershell
cd C:\Users\SEONGMIN\Documents\Workspace\Projects\hobit-ax-agentos
cd agents\agent_hobit_knowledge
```

2. `README.md`와 `contract.md`를 읽습니다.
3. `template.py`를 수정합니다.
4. `tests/test_contract_template.py`를 추가/수정합니다.
5. 루트에서 검증합니다.

```powershell
cd C:\Users\SEONGMIN\Documents\Workspace\Projects\hobit-ax-agentos
pytest agents -q
pytest tests/test_agent_workspaces.py -q
```

이 단계에서는 `src/`를 수정하지 않아도 됩니다.

### 5.2 런타임으로 승격하는 경우

에이전트 템플릿이 충분히 안정화되면 실제 서비스 코드로 옮깁니다.

1. `agents/<agent_id>/contract.md`의 output을 확정합니다.
2. 필요한 경우 `src/hobit_ax_agentos/schemas.py`를 갱신합니다.
3. `src/hobit_ax_agentos/agents/<runtime_file>.py`를 갱신합니다.
4. AgentOS capability가 바뀌면 `src/hobit_ax_agentos/agentos/capabilities.py`를 갱신합니다.
5. Graph shape이 바뀌면 `src/hobit_ax_agentos/agentos/graph_builder.py`를 갱신합니다.
6. 전체 테스트를 실행합니다.

```powershell
pytest -q
```

frontend나 portal 표시가 바뀌면 추가로 실행합니다.

```powershell
cd frontend
npm run lint
npm run build
```

## 6. 계약 변경 절차

계약 변경은 가장 조심해야 합니다. 한 에이전트의 output은 다른 에이전트의 input입니다.

### 계약 변경에 해당하는 경우

- output field 추가, 삭제, rename
- field type 변경
- branch flag 의미 변경
- `requires_action`, `requires_human_review`, `risk_class` 같은 routing field 의미 변경
- `agent.toml`의 `node_id`, `capability_id`, `output_schema` 변경
- graph edge 조건 변경

### 절차

1. 변경하려는 에이전트의 `contract.md`에 `Proposed Change` 섹션을 임시로 적습니다.
2. downstream 에이전트의 `contract.md`를 확인합니다.
3. 영향을 받는 폴더의 담당자와 변경 내용을 합의합니다.
4. `contract.md`와 `template.py`를 같이 수정합니다.
5. 필요한 경우 `schemas.py`, `capabilities.py`, `graph_builder.py`를 수정합니다.
6. `pytest -q`로 전체 검증합니다.
7. 합의가 끝나면 `Proposed Change` 문구를 제거하고 확정 계약만 남깁니다.

## 7. Handoff 규칙

Handoff는 다음 에이전트가 "무엇을 믿고 작업해도 되는지"를 의미합니다.

### Channel Gateway → Coordinator / Persona

- `text`, `user_id`, `session_id`는 비어 있지 않아야 합니다.
- 원본 channel payload는 필요 시 `metadata.raw`로 보존합니다.

### Coordinator → AgentOS Runner

- graph node의 `assigned_agent_id`는 capability manifest와 일치해야 합니다.
- skipped agent는 실행되면 안 됩니다.
- routing reason은 사람이 읽고 납득할 수 있어야 합니다.

### Knowledge → Action

- `requires_action == true`일 때 Action Agent가 실행될 수 있습니다.
- `cited_rule_ids`, `profile_gaps`, `regulation_gaps`는 checklist 생성에 사용됩니다.

### Knowledge → Escalation

- `requires_human_review == true` 또는 high-risk/low-confidence 조건에서 실행됩니다.
- review package에 answer, confidence, cited rules, unresolved points가 포함되어야 합니다.

### Knowledge / Action / Escalation → Final

- Final Agent는 가능한 모든 branch 결과를 받아 user-facing response로 합칩니다.
- human review가 있으면 사용자에게 숨기지 않습니다.

### Final → Outbox / Delivery

- Final Agent는 dispatch하지 않습니다.
- `response`와 `delivery` payload를 만들고, transport는 outbox/dispatcher가 담당합니다.

## 8. 테스트 기준

### 빠른 로컬 검증

```powershell
pytest agents -q
pytest tests/test_agent_workspaces.py -q
```

### 백엔드 전체 검증

```powershell
pytest -q
```

### 프론트 포함 검증

```powershell
cd frontend
npm run lint
npm run build
```

### 권장 수동 smoke

```powershell
python -m hobit_ax_agentos.cli query "복수전공 신청 기간 알려줘" --dry-run
python -m hobit_ax_agentos.cli agents
python -m hobit_ax_agentos.cli smoke-e2e --render-channel web
```

## 9. PR / 리뷰 체크리스트

PR 설명에는 다음 항목을 포함합니다.

- 담당 에이전트 폴더
- 변경 목적
- 변경한 contract field
- downstream 영향
- runtime 승격 여부
- 실행한 테스트 명령

리뷰어는 다음을 확인합니다.

- 담당 폴더 밖 변경이 필요한 변경인가
- `contract.md`와 `template.py`가 일치하는가
- `agent.toml`의 schema/node/capability가 실제 런타임과 충돌하지 않는가
- downstream 에이전트가 깨지지 않는가
- 테스트가 계약 변경을 잡을 수 있는가

## 10. 충돌 방지 규칙

- 같은 에이전트 폴더를 두 명이 동시에 크게 수정하지 않습니다.
- 공통 schema 변경은 작은 PR로 먼저 합의합니다.
- runtime graph 변경과 개별 에이전트 내부 구현 변경을 한 PR에 과하게 섞지 않습니다.
- 다른 에이전트의 output을 임의로 추측하지 않습니다. 반드시 `contract.md`에 있는 field만 사용합니다.

## 11. 새 에이전트 추가 절차

1. `agents/_template/`를 복사합니다.
2. 폴더명을 `agent_hobit_<name>` 형태로 정합니다.
3. `agent.toml`의 `id`, `runtime_module`, `runtime_class`, `node_id`, `capability_id`를 바꿉니다.
4. `contract.md`를 작성합니다.
5. `template.py`와 local test를 작성합니다.
6. `agents/README.md`의 Agent Folders 표에 추가합니다.
7. `tests/test_agent_workspaces.py`의 `EXPECTED_AGENT_FOLDERS`에 추가합니다.
8. graph node라면 `capabilities.py`, `schemas.py`, `graph_builder.py` 반영 여부를 검토합니다.

## 12. 완료 기준

에이전트 작업은 다음을 만족해야 완료로 봅니다.

- 자기 폴더의 계약과 템플릿이 일치합니다.
- required output field가 테스트됩니다.
- downstream handoff가 문서화되어 있습니다.
- `pytest agents -q`가 통과합니다.
- runtime 승격을 했다면 `pytest -q`가 통과합니다.
- UI나 portal에 영향을 줬다면 frontend lint/build 또는 브라우저 확인까지 마칩니다.
