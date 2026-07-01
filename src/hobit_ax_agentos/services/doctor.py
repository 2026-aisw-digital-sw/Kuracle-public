from __future__ import annotations

import importlib
import json
from urllib.error import URLError
from urllib.request import urlopen
from pathlib import Path
from uuid import uuid4

from hobit_ax_agentos.config import AppSettings, bootstrap_local_dependencies


class DoctorService:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()

    def report(self) -> dict:
        bootstrap_local_dependencies(self.settings)
        checks = [
            self._path_check("agentos_repo_path", self.settings.agentos_repo_path),
            self._path_check("agentos_sdk_path", self.settings.agentos_repo_path / "python" / "agentos_sdk"),
            self._path_check(
                "agentos_runtime_path",
                self.settings.agentos_repo_path / "python" / "agentos_runtime",
            ),
            self._path_check("hobit_ax_repo_path", self.settings.hobit_ax_repo_path),
            self._path_check("regulation_rag_path", self.settings.regulation_rag_path),
            self._path_check(
                "regulation_rag_taxonomy",
                self.settings.regulation_rag_path / "configs" / "taxonomy" / "issue_types.json",
            ),
            self._import_check("agentos_sdk"),
            self._import_check("regulation_rag"),
            self._import_check("regulation_rag.workers.supervisor"),
            self._kernel_health_check(),
            self._storage_writable_check(),
        ]
        status = "ok" if all(item["ok"] for item in checks) else "degraded"
        return {
            "status": status,
            "kernel_base_url": self.settings.kernel_base_url,
            "data_dir": str(self.settings.data_dir),
            "enable_action_agent": self.settings.enable_action_agent,
            "checks": checks,
        }

    def readiness(self) -> dict:
        checks = [self._storage_writable_check()]
        return {
            "status": "ready" if all(item["ok"] for item in checks) else "not_ready",
            "checks": checks,
        }

    def _path_check(self, name: str, path: Path) -> dict:
        exists = path.exists()
        return {
            "name": name,
            "kind": "path",
            "ok": exists,
            "path": str(path),
            "message": "exists" if exists else "missing",
        }

    def _import_check(self, module_name: str) -> dict:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            return {
                "name": module_name,
                "kind": "import",
                "ok": False,
                "message": f"{type(exc).__name__}: {exc}",
            }
        return {
            "name": module_name,
            "kind": "import",
            "ok": True,
            "message": "importable",
        }

    def _storage_writable_check(self) -> dict:
        path = self.settings.data_dir
        probe = path / f".write_probe_{uuid4().hex}"
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except Exception as exc:
            return {
                "name": "data_dir_writable",
                "kind": "storage",
                "ok": False,
                "path": str(path),
                "message": f"{type(exc).__name__}: {exc}",
            }
        return {
            "name": "data_dir_writable",
            "kind": "storage",
            "ok": True,
            "path": str(path),
            "message": "writable",
        }

    def _kernel_health_check(self) -> dict:
        url = f"{self.settings.kernel_base_url.rstrip('/')}/health"
        try:
            with urlopen(url, timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, TimeoutError, ValueError) as exc:
            return {
                "name": "kernel_health",
                "kind": "http",
                "ok": False,
                "url": url,
                "message": f"{type(exc).__name__}: {exc}",
            }
        ok = payload.get("status") == "ok"
        return {
            "name": "kernel_health",
            "kind": "http",
            "ok": ok,
            "url": url,
            "message": payload.get("service", "ok") if ok else str(payload),
        }
