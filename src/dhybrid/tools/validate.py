"""Validasi argumen tool via pydantic — gerbang struktural sebelum eksekusi.

Model free kadang mengirim argumen sampah (tipe salah, nilai None untuk argumen
wajib, string kosong). Dulu sampah itu lolos sampai `fn(**arguments)` dan
berujung TypeError aneh / perilaku tak terduga. Di sini argumen diverifikasi
terhadap skema mini ({"type": ..., "required": ...}) dengan pydantic strict
TypeAdapter; yang tidak valid DITOLAK dengan pesan jelas, tidak dieksekusi.

Coercion aman yang diizinkan:
  - int/float -> str   (model kadang kirim angka untuk field string)
  - str angka -> int   (model kadang kirim "42" untuk field integer)
Bukan coercion (ditolak): dict/list/bool untuk string, string non-angka untuk
integer, dsb.
"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

_STR = TypeAdapter(str)
_INT = TypeAdapter(int)
_FLOAT = TypeAdapter(float)
_BOOL = TypeAdapter(bool)
_OBJ = TypeAdapter(dict[str, Any])
_ARR = TypeAdapter(list[Any])


def _check_scalar(ptype: str, key: str, val: Any) -> Any:
    """Cek/coerce satu nilai terhadap tipe mini-schema; raise ValueError bila
    tipe tidak cocok dan tidak bisa di-coerce dengan aman."""
    if ptype == "string":
        if isinstance(val, bool) or val is None:
            raise ValueError(f"argumen '{key}' harus string, dapat {type(val).__name__}")
        if isinstance(val, (int, float)):
            return str(val)  # coercion aman: 42 -> "42"
        try:
            _STR.validate_python(val, strict=True)
        except ValidationError:
            raise ValueError(f"argumen '{key}' harus string, dapat {type(val).__name__}") from None
        return val
    if ptype == "integer":
        if isinstance(val, str):
            if val.strip().lstrip("-").isdigit():
                return int(val)
            raise ValueError(f"argumen '{key}' harus integer, dapat '{val[:40]}'")
        if isinstance(val, bool) or not isinstance(val, int):
            raise ValueError(f"argumen '{key}' harus integer, dapat {type(val).__name__}")
        return val
    if ptype == "number":
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                raise ValueError(f"argumen '{key}' harus angka, dapat '{val[:40]}'") from None
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"argumen '{key}' harus angka, dapat {type(val).__name__}")
        return val
    if ptype == "boolean":
        if isinstance(val, bool):
            return val
        if val in ("true", "True", "1", "ya", "yes"):
            return True
        if val in ("false", "False", "0", "tidak", "no"):
            return False
        raise ValueError(f"argumen '{key}' harus boolean, dapat {type(val).__name__}")
    if ptype == "object":
        try:
            _OBJ.validate_python(val, strict=True)
        except ValidationError:
            raise ValueError(f"argumen '{key}' harus object, dapat {type(val).__name__}") from None
        return val
    if ptype == "array":
        try:
            _ARR.validate_python(val, strict=True)
        except ValidationError:
            raise ValueError(f"argumen '{key}' harus array, dapat {type(val).__name__}") from None
        return val
    return val  # tipe tak dikenal di skema → lewati (jangan blokir)


def validate_args(schema: dict | None, arguments: dict) -> dict:
    """Validasi `arguments` terhadap mini-schema tool; return dict bersih.

    Kunci yang TIDAK ada di skema diteruskan apa adanya (beberapa fn menerima
    **kwargs); kunci di skema diverifikasi tipe + wajib ada.
    """
    if not schema:
        return arguments
    cleaned: dict[str, Any] = {}
    for key, meta in schema.items():
        ptype = (meta or {}).get("type", "string")
        required = bool((meta or {}).get("required", False))
        if key not in arguments or arguments[key] is None:
            if required:
                raise ValueError(f"argumen wajib '{key}' tidak ada")
            continue
        val = arguments[key]
        cleaned[key] = _check_scalar(ptype, key, val)
        min_len = (meta or {}).get("min_length")
        if min_len and isinstance(cleaned[key], str) and len(cleaned[key]) < min_len:
            raise ValueError(
                f"argumen '{key}' terlalu pendek ({len(cleaned[key])} < {min_len} karakter)"
            )
    for key, val in arguments.items():
        if key not in schema:
            cleaned[key] = val  # argumen ekstra → biarkan fn yang memutuskan
    return cleaned
