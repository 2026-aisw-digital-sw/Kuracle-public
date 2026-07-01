# Trigger Agent Contract

## Input

- Deadline watches from `DeadlineWatchStore`.
- Optional regulation source reconciliation result.
- Current date for deterministic deadline checks.

## Output

One or more `TriggerEvent` objects:

- `trigger_id`
- `event_type`
- `user_id`
- `session_id`
- `message`: normalized trigger-origin `IncomingMessage`
- `metadata`: trigger context such as issue type, deadline, days left, source.

## Invariants

- Suppress duplicate daily deadline events per watch.
- Do not directly send notifications; emit events or submit them to the runner.
- Keep proactive recommendations explainable through metadata.

## Handoff

The portal can display the event; the dispatcher can submit it into `ServiceRunner`.
