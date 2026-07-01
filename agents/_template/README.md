# Agent Folder Template

Copy this folder when creating a new Hobit AX agent workspace.

Required files:

- `agent.toml`
- `README.md`
- `contract.md`
- `template.py`
- `tests/test_contract_template.py`

Keep the template self-contained. A contributor should be able to understand the
agent's role, implement the local `run` method, and validate sample payloads without
opening another agent folder.
