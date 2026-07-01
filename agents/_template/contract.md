# Example Agent Contract

## Input

Describe the exact payload keys this agent accepts.

## Output

Describe the exact payload keys this agent returns.

## Invariants

- Do not mutate upstream payloads in place.
- Return JSON-serializable values only.
- Keep external service calls behind small adapter functions.

## Handoff

Describe what the next agent can rely on.
