"""Regresi BUG-04: `create_migration` tidak boleh membuat file duplikat.

Sebelum fix, setiap panggilan `create_migration("create_users_table", ...)`
menulis file baru dengan timestamp berbeda → 60 file identik di migrations/.
Setelah fix: konten (up_sql+down_sql) yang sama → panggilan kedua di-skip,
tetap 1 file. Konten yang BERBEDA → file baru boleh dibuat (perubahan nyata).
"""
import tempfile
from pathlib import Path

from dhybrid.tools.db_migrate import MigrationManager

UP_SQL = "CREATE TABLE users (id SERIAL, name VARCHAR(255) NOT NULL);"


def _mgr():
    d = tempfile.mkdtemp(prefix="dhybrid_migrate_")
    return MigrationManager(d), Path(d)


def test_create_migration_senama_tidak_duplikat():
    mgr, d = _mgr()
    first = mgr.create_migration("create_users_table", UP_SQL, "")
    second = mgr.create_migration("create_users_table", UP_SQL, "")

    files = [p for p in d.glob("*.py")]
    assert len(files) == 1, f"harusnya 1 file, ada {len(files)}"
    assert first.name == second.name == "create_users_table"
    # revision milik panggilan pertama dipertahankan
    assert second.revision == first.revision


def test_create_migration_konten_berbeda_tetap_dibuat():
    mgr, d = _mgr()
    mgr.create_migration("create_users_table", UP_SQL, "")
    mgr.create_migration(
        "create_users_table",
        "CREATE TABLE users (id SERIAL, email VARCHAR(255) UNIQUE);",
        "",
    )

    files = [p for p in d.glob("*.py")]
    assert len(files) == 2, f"konten beda harusnya 2 file, ada {len(files)}"


def test_file_yang_dibuat_bisa_diupgrade():
    mgr, _d = _mgr()
    mgr.create_migration("create_users_table", UP_SQL, "DROP TABLE users")

    # struktur file: berisi up_sql, down_sql, upgrade(), downgrade()
    mgr2 = MigrationManager(mgr.migrations_dir)
    listed = mgr2.list_migrations()
    assert any(lm.name == "create_users_table" for lm in listed)
