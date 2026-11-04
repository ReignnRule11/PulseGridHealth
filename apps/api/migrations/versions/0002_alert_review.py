"""Add alert investigations, response actions, and audit events."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_alert_review"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investigations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alerts.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(30), server_default="in_progress", nullable=False),
        sa.Column("started_by", sa.String(120), nullable=False),
        sa.Column("findings", sa.String(4000)),
        sa.Column("disposition", sa.String(40)),
        sa.Column("resolution_rationale", sa.String(2000)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('in_progress', 'closed')", name="ck_investigation_status"),
    )
    op.create_table(
        "response_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alerts.id"), nullable=False),
        sa.Column("action_type", sa.String(80), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("owner_role", sa.String(100)),
        sa.Column("due_date", sa.Date()),
        sa.Column("status", sa.String(30), server_default="planned", nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'cancelled')", name="ck_response_action_status"),
    )
    op.create_index("ix_response_actions_alert_id", "response_actions", ["alert_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alerts.id"), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("detail", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_alert_id", "audit_logs", ["alert_id"])


def downgrade():
    op.drop_index("ix_audit_logs_alert_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_response_actions_alert_id", table_name="response_actions")
    op.drop_table("response_actions")
    op.drop_table("investigations")
