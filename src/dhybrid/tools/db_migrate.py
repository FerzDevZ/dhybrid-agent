"""Database migration tool - auto-generate and manage Alembic-style migrations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class Migration:
    """Represents a database migration."""
    name: str
    up_sql: str
    down_sql: str
    timestamp: str = ""
    revision: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        if not self.revision:
            self.revision = self.timestamp[:12]


class MigrationManager:
    """Manages database migrations."""

    def __init__(self, migrations_dir: str | Path = "migrations"):
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

    def create_migration(
        self,
        name: str,
        up_sql: str,
        down_sql: str = "",
    ) -> Migration:
        """Create a new migration file."""
        migration = Migration(name=name, up_sql=up_sql, down_sql=down_sql)
        
        filename = f"{migration.timestamp}_{migration.name}.py"
        filepath = self.migrations_dir / filename
        
        content = self._generate_migration_file(migration)
        filepath.write_text(content)
        
        return migration

    def _generate_migration_file(self, migration: Migration) -> str:
        """Generate Python migration file content."""
        return f'''"""Migration: {migration.name}

Revision: {migration.revision}
Created: {migration.timestamp}
"""

up_sql = """
{migration.up_sql}
"""

down_sql = """
{migration.down_sql}
"""

def upgrade(conn):
    """Apply migration."""
    conn.execute(up_sql)

def downgrade(conn):
    """Revert migration."""
    conn.execute(down_sql)
'''

    def list_migrations(self) -> list[Migration]:
        """List all migrations in directory."""
        migrations = []
        for file in sorted(self.migrations_dir.glob("*.py")):
            if file.name.startswith("__"):
                continue
            # Parse migration info from file
            content = file.read_text()
            lines = content.split("\n")
            name = lines[0].replace('"""Migration: ', '').replace('"""', '') if lines else file.stem
            revision = lines[2].replace('Revision: ', '') if len(lines) > 2 else ''
            timestamp = lines[3].replace('Created: ', '') if len(lines) > 3 else ''
            migrations.append(Migration(
                name=name,
                up_sql="",
                down_sql="",
                timestamp=timestamp,
                revision=revision,
            ))
        return migrations


def create_migration(
    name: str,
    up_sql: str,
    down_sql: str = "",
    migrations_dir: str = "migrations",
) -> Migration:
    """Create a new migration file.

    Args:
        name: Migration name (snake_case)
        up_sql: SQL to apply migration
        down_sql: SQL to revert migration (optional)
        migrations_dir: Directory to store migrations

    Returns:
        Created Migration object
    """
    manager = MigrationManager(migrations_dir)
    return manager.create_migration(name, up_sql, down_sql)


def generate_add_table_migration(
    table_name: str,
    columns: list[dict[str, Any]],
    migrations_dir: str = "migrations",
) -> Migration:
    """Generate migration to create a new table.

    Args:
        table_name: Name of table to create
        columns: List of column dicts with keys: name, type, nullable, primary_key, unique, default
        migrations_dir: Directory to store migrations

    Returns:
        Created Migration object
    """
    col_defs = []
    primary_keys = []
    
    for col in columns:
        parts = [col["name"], col["type"]]
        if col.get("primary_key"):
            primary_keys.append(col["name"])
        if not col.get("nullable", True):
            parts.append("NOT NULL")
        if col.get("unique"):
            parts.append("UNIQUE")
        if "default" in col:
            parts.append(f"DEFAULT {col['default']}")
        col_defs.append(" ".join(parts))
    
    if primary_keys:
        col_defs.append(f"PRIMARY KEY ({', '.join(primary_keys)})")
    
    up_sql = f"CREATE TABLE {table_name} (\n    " + ",\n    ".join(col_defs) + "\n)"
    down_sql = f"DROP TABLE {table_name}"
    
    return create_migration(f"create_{table_name}_table", up_sql, down_sql)


def generate_add_column_migration(
    table_name: str,
    column_name: str,
    column_type: str,
    nullable: bool = True,
    default: str | None = None,
    migrations_dir: str = "migrations",
) -> Migration:
    """Generate migration to add a column to existing table."""
    parts = [column_name, column_type]
    if not nullable:
        parts.append("NOT NULL")
    if default:
        parts.append(f"DEFAULT {default}")
    
    col_def = " ".join(parts)
    up_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_def}"
    down_sql = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
    
    return create_migration(f"add_{column_name}_to_{table_name}", up_sql, down_sql)