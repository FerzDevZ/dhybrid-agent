"""Test validasi argumen tool via pydantic (gerbang anti-garbage).

Kelas bug nyata: model free mengirim `terminal(command=</parameter)` /
`find_files(path=-la, pattern=*)` — tipe & konten sampah yang dulu dieksekusi
atau berujung TypeError membingungkan. Sekarang diverifikasi di registry
SEBELUM fn tool dipanggil.
"""

from __future__ import annotations

import pytest

from dhybrid.tools.registry import ToolRegistry
from dhybrid.tools.validate import validate_args

SCHEMA = {
    "command": {"type": "string", "required": True},
    "timeout": {"type": "integer"},
    "verbose": {"type": "boolean"},
    "payload": {"type": "object"},
    "items": {"type": "array"},
    "ratio": {"type": "number"},
}


def test_valid_args_coerced():
    cleaned = validate_args(SCHEMA, {"command": "ls", "timeout": "30"})
    assert cleaned["command"] == "ls"
    assert cleaned["timeout"] == 30  # str-int -> int


def test_int_float_to_string_coerced():
    cleaned = validate_args({"name": {"type": "string"}}, {"name": 42})
    assert cleaned["name"] == "42"


def test_wrong_type_rejected():
    with pytest.raises(ValueError, match="harus integer"):
        validate_args(SCHEMA, {"command": "ls", "timeout": "abc"})
    with pytest.raises(ValueError, match="harus string"):
        validate_args(SCHEMA, {"command": ["ls"]})
    with pytest.raises(ValueError, match="harus object"):
        validate_args(SCHEMA, {"command": "ls", "payload": "not-a-dict"})
    with pytest.raises(ValueError, match="harus boolean"):
        validate_args(SCHEMA, {"command": "ls", "verbose": "maybe"})


def test_required_missing_rejected():
    with pytest.raises(ValueError, match="wajib 'command'"):
        validate_args(SCHEMA, {"timeout": 5})


def test_optional_missing_ok():
    cleaned = validate_args(SCHEMA, {"command": "ls"})
    assert cleaned == {"command": "ls"}


def test_extra_keys_pass_through():
    """Kunci di luar skema diteruskan — fn **kwargs tetap didukung."""
    cleaned = validate_args(SCHEMA, {"command": "ls", "whatever": 1})
    assert cleaned["whatever"] == 1


def test_empty_schema_passthrough():
    assert validate_args({}, {"a": 1}) == {"a": 1}
    assert validate_args(None, {"a": 1}) == {"a": 1}


def test_min_length_enforced():
    with pytest.raises(ValueError, match="terlalu pendek"):
        validate_args({"cmd": {"type": "string", "min_length": 3}}, {"cmd": "x"})


def test_garbage_args_rejected_in_registry_before_fn():
    """Registry menolak argumen sampah dengan pesan jelas, fn TIDAK dipanggil."""
    reg = ToolRegistry(allowlist=[])
    called: list[bool] = []

    def _fake(command: str, timeout: int = 5) -> str:
        called.append(True)
        return f"ok:{command}"

    reg.register("fake", "desc", SCHEMA, _fake)
    out = reg.execute("fake", {"command": "ls", "timeout": "bukan-angka"})
    assert out.startswith("ERROR argumen fake")
    assert not called, "fn tidak boleh dipanggil dengan argumen sampah"

    out = reg.execute("fake", {"timeout": 5})  # command wajib hilang
    assert out.startswith("ERROR argumen fake")
    assert not called

    out = reg.execute("fake", {"command": "ls", "timeout": "7"})
    assert out == "ok:ls"
    assert called == [True]
