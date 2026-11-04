"""Initial aggregate health schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("organization_type", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "communities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("region_code", sa.String(80), nullable=False),
        sa.Column("population_estimate", sa.Integer()),
        sa.UniqueConstraint("organization_id", "region_code"),
    )
    op.create_table(
        "workforce_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("sector", sa.String(100), nullable=False),
        sa.Column("location_code", sa.String(80)),
    )
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_name", sa.String(160), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("provenance", sa.String(500)),
        sa.Column("authorised", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "health_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("workforce_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workforce_groups.id")),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("observed_date", sa.Date(), nullable=False),
        sa.Column("indicator", sa.String(120), nullable=False),
        sa.Column("value", sa.Numeric(14, 4), nullable=False),
        sa.Column("denominator", sa.Integer()),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("(community_id IS NOT NULL AND workforce_group_id IS NULL) OR (community_id IS NULL AND workforce_group_id IS NOT NULL)", name="ck_observation_one_domain"),
        sa.CheckConstraint("value >= 0", name="ck_observation_nonnegative"),
        sa.CheckConstraint("denominator IS NULL OR denominator > 0", name="ck_observation_denominator_positive"),
        sa.UniqueConstraint("source_id", "community_id", "workforce_group_id", "observed_date", "indicator", name="uq_observation_source_group_date_indicator"),
    )
    op.create_index("ix_observations_date_indicator", "health_observations", ["observed_date", "indicator"])
    op.create_table(
        "detection_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("health_observations.id"), nullable=False),
        sa.Column("baseline", sa.Float()),
        sa.Column("anomaly_score", sa.Float()),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(40), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("detection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("detection_results.id"), unique=True, nullable=False)
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending_review", nullable=False),
        sa.Column("explanation", sa.String(2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

def downgrade():
    op.drop_table("alerts")
    op.drop_table("detection_results")
    op.drop_index("ix_observations_date_indicator", table_name="health_observations")
    op.drop_table("health_observations")
    op.drop_table("data_sources")
    op.drop_table("workforce_groups")
    op.drop_table("communities")
    op.drop_table("organizations")
