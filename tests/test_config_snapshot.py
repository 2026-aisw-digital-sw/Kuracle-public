from __future__ import annotations

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.services.config_snapshot import ConfigSnapshotService


def test_config_snapshot_redacts_api_token(tmp_path) -> None:
    settings = AppSettings(
        data_dir=tmp_path / "data",
        api_token="secret-token",
        enable_action_agent=False,
        rate_limit_per_minute=30,
    )

    snapshot = ConfigSnapshotService(settings).snapshot()

    assert snapshot["kernel"]["api_token_configured"] is True
    assert "secret-token" not in str(snapshot)
    assert snapshot["runtime"]["enable_action_agent"] is False
    assert snapshot["runtime"]["action_agent_mode"] == (
        "disabled_until_contract_studio_bridge"
    )
    assert snapshot["runtime"]["rate_limit_per_minute"] == 30
    assert snapshot["paths"]["data_dir"] == str(tmp_path / "data")


def test_config_snapshot_marks_enabled_action_agent(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path / "data", enable_action_agent=True)

    snapshot = ConfigSnapshotService(settings).snapshot()

    assert snapshot["kernel"]["api_token_configured"] is False
    assert snapshot["runtime"]["action_agent_mode"] == "enabled"
