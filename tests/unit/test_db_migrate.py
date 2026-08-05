"""Tests for database migration tool."""
from dhybrid.tools.db_migrate import (
    Migration,
    create_migration,
    generate_add_table_migration,
)


def test_migration_has_up_and_down():
    """Test that migration has both up and down SQL."""
    migration = Migration(
        name="create_users",
        up_sql="CREATE TABLE users (id SERIAL PRIMARY KEY, name VARCHAR(255))",
        down_sql="DROP TABLE users",
    )
    assert "CREATE TABLE users" in migration.up_sql
    assert "DROP TABLE users" in migration.down_sql


def test_create_migration_add_table(tmp_path):
    """Test creating a migration for adding a users table."""
    migration = create_migration(
        name="create_users",
        up_sql="CREATE TABLE users (id SERIAL PRIMARY KEY, name VARCHAR(255))",
        down_sql="DROP TABLE users",
        migrations_dir=str(tmp_path),
    )
    assert migration.name == "create_users"
    assert "CREATE TABLE users" in migration.up_sql
    assert "DROP TABLE users" in migration.down_sql
    assert (tmp_path / f"{migration.timestamp}_create_users.py").exists()


def test_generate_add_table_migration():
    """Test generating migration for a users table with columns."""
    columns = [
        {"name": "id", "type": "SERIAL", "primary_key": True},
        {"name": "name", "type": "VARCHAR(255)", "nullable": False},
        {"name": "email", "type": "VARCHAR(255)", "unique": True},
        {"name": "created_at", "type": "TIMESTAMP", "default": "NOW()"},
    ]
    migration = generate_add_table_migration("users", columns)
    assert "CREATE TABLE users" in migration.up_sql
    assert "id SERIAL" in migration.up_sql
    assert "name VARCHAR(255) NOT NULL" in migration.up_sql
    assert "email VARCHAR(255) UNIQUE" in migration.up_sql
    assert "created_at TIMESTAMP DEFAULT NOW()" in migration.up_sql
    assert "PRIMARY KEY (id)" in migration.up_sql
    assert migration.down_sql == "DROP TABLE users"