from __future__ import annotations

from hobit_ax_agentos.config import AppSettings


class ConfigSnapshotService:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()

    def snapshot(self) -> dict:
        return {
            "paths": {
                "agentos_repo_path": str(self.settings.agentos_repo_path),
                "hobit_ax_repo_path": str(self.settings.hobit_ax_repo_path),
                "regulation_rag_path": str(self.settings.regulation_rag_path),
                "data_dir": str(self.settings.data_dir),
            },
            "kernel": {
                "base_url": self.settings.kernel_base_url,
                "api_token_configured": self.settings.api_token is not None,
            },
            "tenant": {
                "tenant_id": self.settings.tenant_id,
                "default_user_id": self.settings.default_user_id,
                "default_session_id": self.settings.default_session_id,
            },
            "runtime": {
                "confidence_threshold": self.settings.confidence_threshold,
                "enable_action_agent": self.settings.enable_action_agent,
                "action_agent_mode": (
                    "enabled"
                    if self.settings.enable_action_agent
                    else "disabled_until_contract_studio_bridge"
                ),
                "rate_limit_per_minute": self.settings.rate_limit_per_minute,
            },
        }
