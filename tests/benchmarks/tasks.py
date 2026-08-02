"""Benchmark tasks — 5 task coding standar untuk mengukur hemat token."""

# Setiap task: {"name", "prompt", "setup" (shell, dijalankan di tmpdir), "verify" (shell, exit 0 = sukses)}

TASKS = [
    {
        "name": "fix-bug-kecil",
        "setup": (
            "printf 'def add(a, b):\\n    return a - b\\n\\n"
            "def test_add():\\n    assert add(2, 3) == 5\\n' > calc.py\n"
            "printf 'import pytest\\n' > /dev/null"
        ),
        "prompt": "Ada bug di calc.py: fungsi add mengurangkan bukan menjumlahkan. Perbaiki dengan edit minimal lalu jalankan test sampai hijau.",
        "verify": "python3 -c 'from calc import add; assert add(2,3)==5'",
    },
    {
        "name": "tambah-fungsi-dengan-test",
        "setup": "printf 'def mul(a, b):\\n    return a * b\\n' > calc.py",
        "prompt": "Tambahkan fungsi `div(a, b)` di calc.py yang membagi (tolak b==0 dengan ValueError) BESERTA test-nya, TDD style. Pastikan test hijau.",
        "verify": "python3 -c 'from calc import div; assert div(10,2)==5'",
    },
    {
        "name": "refactor-kecil",
        "setup": (
            "printf 'def process(x):\\n    t = x + 1\\n    t = t * 2\\n    t = t - 3\\n"
            "    return t\\n' > proc.py"
        ),
        "prompt": "Sederhanakan process() di proc.py tanpa mengubah hasil akhir. Edit minimal.",
        "verify": "python3 -c 'from proc import process; assert process(5)==9'",
    },
    {
        "name": "cari-dan-ganti",
        "setup": (
            "mkdir -p pkg\n"
            "for i in 1 2 3; do printf 'VERSION = \"0.0.1\"\\n' > pkg/v$i.py; done"
        ),
        "prompt": "Ganti semua VERSION = \"0.0.1\" menjadi \"1.2.3\" di direktori pkg/ (3 file).",
        "verify": "grep -r '1.2.3' pkg/ | wc -l | grep -q 3",
    },
    {
        "name": "tulis-readme",
        "setup": "printf 'def hello():\n    return \"hello\"\n' > lib.py",
        "prompt": "Tulis README.md singkat (10-15 baris) untuk project kecil ini: nama 'lib', fungsi hello().",
        "verify": "test -s README.md && grep -qi 'hello' README.md",
    },
]
