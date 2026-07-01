from __future__ import annotations

import json

import pytest

from hobit_ax_agentos.cli import _load_payload


def test_load_payload_from_inline_json() -> None:
    assert _load_payload('{"text": "hello"}', None) == {"text": "hello"}


def test_load_payload_from_file(tmp_path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"message": "hello"}), encoding="utf-8")

    assert _load_payload(None, str(payload)) == {"message": "hello"}


def test_load_payload_from_utf8_bom_file(tmp_path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text('\ufeff{"message": "hello"}', encoding="utf-8")

    assert _load_payload(None, str(payload)) == {"message": "hello"}


def test_load_payload_rejects_ambiguous_sources(tmp_path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit):
        _load_payload("{}", str(payload))


def test_load_payload_requires_source() -> None:
    with pytest.raises(SystemExit):
        _load_payload(None, None)


def test_load_payload_reports_invalid_inline_json() -> None:
    with pytest.raises(SystemExit, match="Invalid JSON in --payload"):
        _load_payload("{message: bad}", None)
