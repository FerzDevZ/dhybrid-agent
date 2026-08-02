---
name: python-modern
description: Python modern, stdlib, type hints, dataclass, idiomatik
---

# Python Modern & Idiomatik

- Pakai stdlib dulu (pathlib, dataclasses, functools, itertools) sebelum library.
- Type hints: `def f(x: int) -> str:` + `from __future__ import annotations`.
- `dataclass` untuk struktur data, bukan dict yang rapuh.
- Context manager `with` untuk resource (file, koneksi).
- `f-string` untuk format; hindari concatenation berantai.
- List/dict comprehension bila jelas; jangan dipaksakan.

Jangan: menulis ulang kode yang sudah berfungsi hanya agar "lebih modern"
(lazy rule: kalau tidak diminta, jangan sentuh).
