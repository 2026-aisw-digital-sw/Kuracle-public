# Hobit AX Multi-Agent Workspaces

This directory is the collaboration surface for building Hobit AX as a multi-agent
system on AgentOS. Each agent has its own folder so separate contributors can work
without editing another agent's files.

Runtime code still lives under `src/hobit_ax_agentos/agents` until an agent folder
graduates into production wiring. The files here define the agent contract and the
implementation template that each contributor should follow.

Detailed collaboration rules are documented in
`docs/multi-agent-collaboration-manual.md`.

## Agent Folders

| Folder | Runtime role | AgentOS node |
| --- | --- | --- |
| `agent_hobit_channel_gateway` | Normalize inbound channels into `IncomingMessage` | pre-graph |
| `hobit_coordinator` | Build the AgentOS task graph and routing plan | planner |
| `agent_hobit_persona` | Build reusable session/persona context | prefetch worker |
| `agent_hobit_trigger` | Emit proactive administrative trigger messages | trigger worker |
| `agent_hobit_knowledge` | Answer regulation questions through regulation RAG | `knowledge_query` |
| `agent_hobit_action` | Prepare action plans, drafts, and checklists | `action_prepare` |
| `agent_hobit_escalation` | Package low-confidence/high-risk cases for human review | `escalation_prepare` |
| `agent_hobit_final` | Compose final user-facing response and delivery payload | `final_response` |

## Folder Contract

Every agent folder must contain:

- `agent.toml`: machine-readable ownership, AgentOS node, schemas, and dependencies.
- `README.md`: human-readable role, responsibilities, and local workflow.
- `contract.md`: precise input/output and handoff contract.
- `template.py`: starter implementation skeleton for that agent only.
- `tests/test_contract_template.py`: local contract test scaffold for that agent.

## Working Rule

Contributors should modify only their assigned `agents/<agent_folder>/` folder unless
they are explicitly changing a shared AgentOS contract. Cross-agent changes must be
proposed through `docs/multi-agent-development.md` first.
