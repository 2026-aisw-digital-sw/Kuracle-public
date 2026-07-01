# Action Agent Contract

## Input

- Knowledge Agent output.
- Optional user profile and channel context.

## Output

Must satisfy `ACTION_OUTPUT_SCHEMA`:

- `action_plan`: object containing title, checklist, cited rules, and optional draft.
- `requires_human_approval`: boolean.

## Invariants

- Do not submit forms or perform irreversible actions.
- High-risk actions require human approval.
- Keep generated drafts traceable to cited regulation IDs.

## Handoff

Final Agent can embed the action plan in the user-facing response or delivery payload.
