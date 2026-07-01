# Escalation Agent Contract

## Input

- Knowledge Agent output.
- Run context containing session, user, run, and trace identifiers.

## Output

Must satisfy `ESCALATION_OUTPUT_SCHEMA`:

- `requires_human_review`
- `reason`
- `escalation_id`
- `review_package`

## Invariants

- Persist every escalation before returning it.
- Include enough context for a reviewer to reproduce the issue.
- Do not resolve or approve a case during creation.

## Handoff

Final Agent can tell the user that a human review is in progress and include the
case in delivery metadata.
