# Knowledge Agent Contract

## Input

- `message`: normalized `IncomingMessage` dict.
- Optional `query` override.
- Optional profile in `message.metadata.profile`.

## Output

Must satisfy `KNOWLEDGE_OUTPUT_SCHEMA`:

- `answer`
- `confidence`
- `requires_action`
- `requires_human_review`
- `risk_class`
- `cited_rule_ids`
- `cited_articles`
- `cited_content_sources`
- `workflow_status`
- `intent_mode`
- `request_type`
- `issue_types`
- `coverage_report`
- `profile_gaps`
- `regulation_gaps`
- `unresolved_points`
- `regulation_rag_trace_id`
- `state`

## Invariants

- Keep Hobit-specific RAG details behind the adapter boundary.
- Always return JSON-serializable output.
- Set review/action booleans explicitly; downstream agents branch on them.

## Handoff

Action, Escalation, and Final agents can rely on confidence, review/action flags,
citations, issue types, and answer text.
