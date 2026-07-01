from __future__ import annotations

KNOWLEDGE_OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "answer",
        "confidence",
        "requires_action",
        "requires_human_review",
        "risk_class",
    ],
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number"},
        "requires_action": {"type": "boolean"},
        "requires_human_review": {"type": "boolean"},
        "risk_class": {"type": "string"},
        "cited_rule_ids": {"type": "array", "items": {"type": "string"}},
        "cited_content_sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "issuing_office": {"type": ["string", "null"]},
                },
            },
        },
        "workflow_status": {"type": "string"},
        "regulation_rag_trace_id": {},  # string when recorded, null on adapter failure
    },
}

ACTION_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["action_plan", "requires_human_approval"],
    "properties": {
        "action_plan": {"type": "object"},
        "requires_human_approval": {"type": "boolean"},
    },
}

ESCALATION_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["requires_human_review", "reason", "review_package"],
    "properties": {
        "requires_human_review": {"type": "boolean"},
        "reason": {"type": "string"},
        "review_package": {"type": "object"},
    },
}

FINAL_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["response"],
    "properties": {
        "response": {"type": "string"},
        "delivery": {"type": "object"},
    },
}
