from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PROJECTS_ROOT = Path(r"C:\Users\SEONGMIN\Documents\Workspace\Projects")

# regulation_rag's own workers/_llm.py loads hobit-ax/.env lazily, the first time an
# LLM call happens deep inside Supervisor — by then AppSettings' field defaults below
# (evaluated once, at module import time) have already been computed. Load the same
# .env file here, before those defaults run, so OPENAI_API_KEY etc. are visible to
# AppSettings too (e.g. for hybrid retrieval client construction).
try:
    from dotenv import load_dotenv

    load_dotenv(
        Path(os.getenv("HOBIT_AX_REPO_PATH", str(DEFAULT_PROJECTS_ROOT / "hobit-ax"))) / ".env"
    )
except ImportError:
    pass


@dataclass(slots=True)
class AppSettings:
    agentos_repo_path: Path = Path(
        os.getenv("AGENTOS_REPO_PATH", str(DEFAULT_PROJECTS_ROOT / "agent-os"))
    )
    hobit_ax_repo_path: Path = Path(
        os.getenv("HOBIT_AX_REPO_PATH", str(DEFAULT_PROJECTS_ROOT / "hobit-ax"))
    )
    kernel_base_url: str = os.getenv("AGENTOS_KERNEL_URL", "http://127.0.0.1:8765")
    api_token: str | None = os.getenv("AGENTOS_API_TOKEN") or None
    tenant_id: str = os.getenv("HOBIT_TENANT_ID", "hobit-local")
    default_user_id: str = os.getenv("HOBIT_USER_ID", "local-user")
    default_session_id: str = os.getenv("HOBIT_SESSION_ID", "local-session")
    confidence_threshold: float = float(os.getenv("HOBIT_CONFIDENCE_THRESHOLD", "0.7"))
    data_dir: Path = Path(os.getenv("HOBIT_AGENTOS_DATA_DIR", "data"))
    enable_action_agent: bool = os.getenv("HOBIT_ENABLE_ACTION_AGENT", "false").lower() == "true"
    rate_limit_per_minute: int = int(os.getenv("HOBIT_RATE_LIMIT_PER_MINUTE", "0"))
    # Optional hybrid (dense+sparse) retrieval backend for regulation_rag's content
    # layer. Mirrors regulation_rag's own api/main.py default: prefer a local
    # file-mode Qdrant store (no server needed) and only use a remote URL if one is
    # explicitly set. openai_api_key must also be set for Supervisor to use it;
    # otherwise it falls back to sparse-only retrieval automatically (Supervisor's
    # own use_hybrid gate).
    qdrant_url: str | None = os.getenv("HOBIT_QDRANT_URL") or None
    qdrant_path: str | None = os.getenv("HOBIT_QDRANT_PATH") or None
    qdrant_collection: str = os.getenv("HOBIT_QDRANT_COLLECTION", "hobit_ax_content")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None

    @property
    def regulation_rag_path(self) -> Path:
        return self.hobit_ax_repo_path / "regulation_rag"

    @property
    def qdrant_local_path(self) -> Path:
        return Path(self.qdrant_path) if self.qdrant_path else self.regulation_rag_path / "data" / "qdrant_store"


def bootstrap_local_dependencies(settings: AppSettings | None = None) -> None:
    """Make local AgentOS and hobit-ax packages importable without installation."""
    settings = settings or AppSettings()
    candidates = [
        settings.agentos_repo_path / "python" / "agentos_sdk",
        settings.agentos_repo_path / "python" / "agentos_runtime",
        settings.hobit_ax_repo_path,
    ]
    for path in candidates:
        if path.exists():
            path_str = str(path)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)
