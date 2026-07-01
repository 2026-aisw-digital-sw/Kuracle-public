# Trigger Agent

Creates proactive administrative events, such as "this deadline is near" or
"a watched regulation changed". Trigger output becomes a normal `IncomingMessage`
so the rest of AgentOS can handle it through the same graph.

Runtime reference: `src/hobit_ax_agentos/agents/trigger.py`.
