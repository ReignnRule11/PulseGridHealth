"""Add upload provenance, notifications and reviewer assignment."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_upload_activity"
down_revision = "0006_organization_access_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "data_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerts_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_data_import_batches_organization_id", "data_import_batches", ["organization_id"])
    op.create_index("ix_data_import_batches_uploaded_by_user_id", "data_import_batches", ["uploaded_by_user_id"])
    op.add_column("health_observations", sa.Column(
        "import_batch_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("data_import_batches.id"), nullable=True
    ))
    op.create_index("ix_health_observations_import_batch_id", "health_observations", ["import_batch_id"])
    op.add_column("alerts", sa.Column(
        "assigned_to_user_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id"), nullable=True
    ))
    op.add_column("alerts", sa.Column(
        "assigned_by_user_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id"), nullable=True
    ))
    op.create_index("ix_alerts_assigned_to_user_id", "alerts", ["assigned_to_user_id"])
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("related_type", sa.String(40)),
        sa.Column("related_id", postgresql.UUID(as_uuid=True)),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_notifications_organization_id", "notifications", ["organization_id"])
    op.create_index("ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])

    # Enforce tenant isolation in PostgreSQL for both new organization-scoped tables.
    for table in ("data_import_batches", "notifications"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid)
            WITH CHECK (organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid)
        """)


def downgrade():
    for table in ("notifications", "data_import_batches"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_notifications_recipient_user_id", table_name="notifications")
    op.drop_index("ix_notifications_organization_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_alerts_assigned_to_user_id", table_name="alerts")
    op.drop_column("alerts", "assigned_by_user_id")
    op.drop_column("alerts", "assigned_to_user_id")
    op.drop_index("ix_health_observations_import_batch_id", table_name="health_observations")
    op.drop_column("health_observations", "import_batch_id")
    op.drop_index("ix_data_import_batches_uploaded_by_user_id", table_name="data_import_batches")
    op.drop_index("ix_data_import_batches_organization_id", table_name="data_import_batches")
    op.drop_table("data_import_batches")
