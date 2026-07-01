from __future__ import annotations

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.services import doctor as doctor_module
from hobit_ax_agentos.services.doctor import DoctorService


def test_doctor_reports_degraded_for_missing_paths(tmp_path) -> None:
    settings = AppSettings(
        agentos_repo_path=tmp_path / "missing-agentos",
        hobit_ax_repo_path=tmp_path / "missing-hobit",
        data_dir=tmp_path / "data",
    )

    report = DoctorService(settings).report()

    assert report["status"] == "degraded"
    assert report["data_dir"] == str(tmp_path / "data")
    assert any(
        check["name"] == "agentos_repo_path" and check["ok"] is False
        for check in report["checks"]
    )
    assert any(
        check["name"] == "regulation_rag_path" and check["ok"] is False
        for check in report["checks"]
    )
    assert any(
        check["name"] == "data_dir_writable" and check["ok"] is True
        for check in report["checks"]
    )


def test_doctor_reports_existing_paths(tmp_path) -> None:
    agentos = tmp_path / "agent-os"
    hobit = tmp_path / "hobit-ax"
    (agentos / "python" / "agentos_sdk").mkdir(parents=True)
    (agentos / "python" / "agentos_runtime").mkdir(parents=True)
    (hobit / "regulation_rag" / "configs" / "taxonomy").mkdir(parents=True)
    (hobit / "regulation_rag" / "configs" / "taxonomy" / "issue_types.json").write_text(
        "{}",
        encoding="utf-8",
    )
    settings = AppSettings(agentos_repo_path=agentos, hobit_ax_repo_path=hobit)

    report = DoctorService(settings).report()
    path_checks = {check["name"]: check for check in report["checks"] if check["kind"] == "path"}

    assert path_checks["agentos_repo_path"]["ok"] is True
    assert path_checks["agentos_sdk_path"]["ok"] is True
    assert path_checks["regulation_rag_taxonomy"]["ok"] is True


def test_doctor_readiness_uses_storage_writability(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path / "data")

    readiness = DoctorService(settings).readiness()

    assert readiness["status"] == "ready"
    assert readiness["checks"][0]["name"] == "data_dir_writable"
    assert readiness["checks"][0]["ok"] is True


def test_doctor_reports_kernel_health_error(tmp_path) -> None:
    settings = AppSettings(
        data_dir=tmp_path / "data",
        kernel_base_url="http://127.0.0.1:1",
    )

    report = DoctorService(settings).report()
    kernel = next(check for check in report["checks"] if check["name"] == "kernel_health")

    assert report["status"] == "degraded"
    assert kernel["ok"] is False
    assert kernel["url"] == "http://127.0.0.1:1/health"


def test_doctor_reports_kernel_health_ok(tmp_path, monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"status":"ok","service":"agentos-kernel"}'

    def fake_urlopen(url, timeout):
        assert url == "http://kernel.local/health"
        assert timeout == 1.0
        return FakeResponse()

    monkeypatch.setattr(doctor_module, "urlopen", fake_urlopen)
    settings = AppSettings(
        data_dir=tmp_path / "data",
        kernel_base_url="http://kernel.local",
    )

    report = DoctorService(settings).report()
    kernel = next(check for check in report["checks"] if check["name"] == "kernel_health")

    assert kernel["ok"] is True
    assert kernel["message"] == "agentos-kernel"
