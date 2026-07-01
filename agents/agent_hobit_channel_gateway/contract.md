# Channel Gateway Contract

## Input

- `channel`: API route segment or adapter name such as `api`, `web`, `portal`, `kakao`.
- `payload`: arbitrary JSON object from that channel.
- Optional auth/session metadata from the API layer.

## Output

An `IncomingMessage` compatible object:

- `channel`: normalized channel name.
- `user_id`: stable user identifier.
- `session_id`: stable session identifier.
- `text`: user-visible request text.
- `metadata`: JSON object containing channel-specific details, profile hints, and idempotency keys.

## Invariants

- Never call regulation RAG or LLMs.
- Never decide the graph shape.
- Preserve raw channel details under `metadata.raw` when useful for audit.

## Handoff

`hobit_coordinator` and `agent_hobit_persona` can assume `text`, `user_id`, and
`session_id` are non-empty strings.
