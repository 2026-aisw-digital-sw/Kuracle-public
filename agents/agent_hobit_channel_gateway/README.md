# Channel Gateway Agent

Normalizes external channel payloads into the single `IncomingMessage` shape used
by the rest of Hobit AX.

Own this folder when changing channel-specific parsing, metadata normalization,
or user/session identity mapping. Do not add domain reasoning here; pass domain
signals through metadata for downstream agents.

Runtime reference: `src/hobit_ax_agentos/agents/channel_gateway.py`.
