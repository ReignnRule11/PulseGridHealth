"""Add tenant keys and PostgreSQL row-level security to health data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_tenant_isolation"
down_revision = "0003_identity_access"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "data_sources", "health_observations", "detection_results", "alerts",
    "investigations", "response_actions", "audit_logs",
]


def upgrade():
    op.add_column("data_sources", sa.Column("organization_id", postgresql.UUID(as_uuid=True)))
    op.add_column("health_observations", sa.Column("organization_id", postgresql.UUID(as_uuid=True)))
    op.add_column("detection_results", sa.Column("organization_id", postgresql.UUID(as_uuid=True)))
    op.add_column("alerts", sa.Column("organization_id", postgresql.UUID(as_uuid=True)))
    op.add_column("investigations", sa.Column("organization_id", postgresql.UUID(as_uuid=True)))
    op.add_column("response_actions", sa.Column("organization_id", postgresql.UUID(as_uuid=True)))
    op.add_column("audit_logs", sa.Column("organization_id", postgresql.UUID(as_uuid=True)))

    op.execute("""
        INSERT INTO organizations (id, name, organization_type, created_at)
        SELECT gen_random_uuid(), 'PulseGrid Demonstration', 'demo', now()
        WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE name = 'PulseGrid Demonstration')
    """)
    op.execute("""
        UPDATE data_sources SET organization_id =
          (SELECT id FROM organizations WHERE name = 'PulseGrid Demonstration')
        WHERE organization_id IS NULL
    """)
    op.execute("""
        UPDATE health_observations h SET organization_id =
          COALESCE(c.organization_id, w.organization_id)
        FROM communities c FULL JOIN workforce_groups w ON false
        WHERE (h.community_id = c.id OR h.workforce_group_id = w.id)
          AND h.organization_id IS NULL
    """)
    op.execute("""
        UPDATE detection_results d SET organization_id = h.organization_id
        FROM health_observations h WHERE d.observation_id = h.id AND d.organization_id IS NULL
    """)
    op.execute("""
        UPDATE alerts a SET organization_id = d.organization_id
        FROM detection_results d WHERE a.detection_id = d.id AND a.organization_id IS NULL
    """)
    for table in ("investigations", "response_actions", "audit_logs"):
        op.execute(f"""
            UPDATE {table} child SET organization_id = parent.organization_id
            FROM alerts parent WHERE child.alert_id = parent.id AND child.organization_id IS NULL
        """)
    for table in TENANT_TABLES:
        op.alter_column(table, "organization_id", nullable=False)
        op.create_foreign_key(f"fk_{table}_organization", table, "organizations", ["organization_id"], ["id"])
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid)
            WITH CHECK (organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid)
        """)


def downgrade():
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organization", table, type_="foreignkey")
        op.drop_column(table, "organization_id")
