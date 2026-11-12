"""Add organization member-management audit history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_organization_access_audit"
down_revision = "0005_account_action_tokens"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_access_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("after_state", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_organization_access_audit_organization_id", "organization_access_audit", ["organization_id"])
    op.create_index("ix_organization_access_audit_actor_user_id", "organization_access_audit", ["actor_user_id"])


def downgrade():
    op.drop_index("ix_organization_access_audit_actor_user_id", table_name="organization_access_audit")
    op.drop_index("ix_organization_access_audit_organization_id", table_name="organization_access_audit")
    op.drop_table("organization_access_audit")
