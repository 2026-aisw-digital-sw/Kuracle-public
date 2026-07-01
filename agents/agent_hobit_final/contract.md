# Final Response Agent Contract

## Input

- `knowledge`: Knowledge Agent output.
- Optional `action`: Action Agent output.
- Optional `escalation`: Escalation Agent output.
- `channel`: target delivery channel.

## Output

Must satisfy `FINAL_OUTPUT_SCHEMA`:

- `response`: final user-facing text.
- `delivery`: channel payload metadata including optional action plan and escalation.

## Invariants

- Never hide human-review status from the user.
- Keep response text safe for the target channel.
- Do not dispatch delivery directly; write through outbox path.

## Handoff

Delivery renderer and user portal can display `response` and inspect `delivery`.
