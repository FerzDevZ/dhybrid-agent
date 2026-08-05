"""Migration: create_users_table

Revision: 20260805_053
Created: 20260805_053418
"""

up_sql = """
CREATE TABLE users (
    id SERIAL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (id)
)
"""

down_sql = """
DROP TABLE users
"""

def upgrade(conn):
    """Apply migration."""
    conn.execute(up_sql)

def downgrade(conn):
    """Revert migration."""
    conn.execute(down_sql)
