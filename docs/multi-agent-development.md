# Multi-Agent Development Guide

## Purpose

Hobit AX is implemented as a multi-agent service on top of AgentOS. AgentOS owns
execution, leasing, graph validation, policy, trace, and durable state. Hobit AX
owns domain behavior: regulation reasoning, proactive administrative alerts,
action drafts, escalation packages, and user-facing delivery.

The development model is folder-oriented: each contributor works in one
`agents/<agent_id>/` workspace and treats the files in that folder as their local
source of truth.

For the detailed team workflow, review
`docs/multi-agent-collaboration-manual.md`.

## Agent Layers

### Intake and Planning

- `agent_hobit_channel_gateway` converts API, web, portal, KakaoTalk, or generic
  inputs into a normalized `IncomingMessage`.
- `hobit_coordinator` classifies the request, builds the task graph, persists the
  selected/skipped agent plan, and records routing reasons.
- `agent_hobit_persona` builds reusable session context and predicted follow-up
  questions before or beside graph execution.
- `agent_hobit_trigger` emits proactive administrative messages, currently from
  deadline watches and regulation-change checks.

### AgentOS Graph Nodes

- `agent_hobit_knowledge` runs the regulation RAG adapter and returns a structured
  knowledge result.
- `agent_hobit_action` prepares checklists, form drafts, and action plans when the
  knowledge result says action is required.
- `agent_hobit_escalation` packages high-risk or low-confidence results for human
  review.
- `agent_hobit_final` composes the final user-facing response and delivery payload.

## Collaboration Rules

1. Work inside your assigned `agents/<agent_id>/` folder first.
2. Do not change another agent's contract without updating both folders and this
   guide.
3. Keep `agent.toml` machine-readable. It is used by tests to verify workspace
   completeness.
4. Keep `contract.md` precise. Downstream agents should not need to infer payload
   fields from implementation code.
5. Keep `template.py` runnable as a local skeleton. Production wiring can later
   move logic into `src/hobit_ax_agentos/agents`.

Detailed role boundaries, contract-change process, handoff rules, and PR checklist
are maintained in `docs/multi-agent-collaboration-manual.md`.

## Promotion Path

1. Fill in the agent folder template and local tests.
2. Add or update JSON schema in `src/hobit_ax_agentos/schemas.py` if the output
   contract changes.
3. Update capability metadata in `src/hobit_ax_agentos/agentos/capabilities.py`.
4. Update graph wiring in `src/hobit_ax_agentos/agentos/graph_builder.py` only if
   the AgentOS DAG shape changes.
5. Run `pytest -q` and, for frontend-facing changes, `npm run lint` and
   `npm run build` in `frontend/`.
