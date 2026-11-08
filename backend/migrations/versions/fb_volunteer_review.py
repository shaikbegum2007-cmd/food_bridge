"""Add volunteer contact details and administrator review."""

from alembic import op
import sqlalchemy as sa


revision = "fb_volunteer_review"
down_revision = "abf0090afac5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "volunteer_profiles",
        sa.Column("phone", sa.String(length=30), server_default="", nullable=False),
    )
    op.add_column(
        "volunteer_profiles",
        sa.Column("verification_status", sa.String(length=20), server_default="pending", nullable=False),
    )
    op.create_index(
        op.f("ix_volunteer_profiles_verification_status"),
        "volunteer_profiles",
        ["verification_status"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_volunteer_profiles_verification_status"), table_name="volunteer_profiles")
    op.drop_column("volunteer_profiles", "verification_status")
    op.drop_column("volunteer_profiles", "phone")
