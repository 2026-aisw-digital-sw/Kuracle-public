# Coordinator Contract

## Input

- Normalized `IncomingMessage`.
- Optional `PersonaSnapshot`.
- Runtime settings such as whether Action Agent is enabled.

## Output

- AgentOS `TaskGraphIR` with node assignments.
- Persisted `CoordinationPlan` containing selected agents, skipped agents, routing
  reasons, persona summary, and graph nodes.

## Invariants

- Coordinator chooses graph structure but does not execute graph nodes.
- Action Agent is skipped unless explicitly enabled.
- Every graph node must map to a declared capability.

## Handoff

`ServiceRunner` can validate leased nodes against the persisted plan.
