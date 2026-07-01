# Persona Worker Contract

## Input

- `IncomingMessage`.
- Recent conversation history for the same session.

## Output

- `session_id`
- `user_id`
- `top_issue_types`
- `predicted_questions`
- `profile`

## Invariants

- First-pass implementation must be deterministic.
- Do not block the main request on slow external calls.
- Do not store sensitive raw messages outside approved stores.

## Handoff

Coordinator can use issue types as a hint; the portal can display predicted questions.
