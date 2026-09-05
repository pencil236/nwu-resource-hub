"""Add resource metadata, reactions, onboarding and help requests."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0003"
down_revision = "20260905_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    resource_columns = (
        sa.Column("resource_type", sa.String(40), nullable=False, server_default="其他"),
        sa.Column("college", sa.String(100), nullable=False, server_default="通用"),
        sa.Column("major", sa.String(100), nullable=False, server_default="通用"),
        sa.Column("teacher", sa.String(100), nullable=False, server_default="通用"),
        sa.Column("grade", sa.String(40), nullable=False, server_default="通用"),
        sa.Column("year", sa.Integer()),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dislike_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("report_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    for column in resource_columns:
        op.add_column("resources", column)
    for column in ("resource_type", "college", "major", "teacher", "grade", "year"):
        op.create_index(f"ix_resources_{column}", "resources", [column])

    op.create_table(
        "resource_dislikes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resource_id",
            sa.String(36),
            sa.ForeignKey("resources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("resource_id", "user_id", name="uq_resource_dislike"),
    )
    op.create_index("ix_resource_dislikes_resource_id", "resource_dislikes", ["resource_id"])
    op.create_index("ix_resource_dislikes_user_id", "resource_dislikes", ["user_id"])

    op.create_table(
        "resource_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "author_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("college", sa.String(100), nullable=False),
        sa.Column("major", sa.String(100), nullable=False),
        sa.Column("course", sa.String(120), nullable=False),
        sa.Column("heat_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("author_id", "title", "college", "major", "course"):
        op.create_index(f"ix_resource_requests_{column}", "resource_requests", [column])
    op.create_table(
        "resource_request_supports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("resource_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id", "user_id", name="uq_resource_request_support"),
    )
    op.create_index(
        "ix_resource_request_supports_request_id",
        "resource_request_supports",
        ["request_id"],
    )
    op.create_index(
        "ix_resource_request_supports_user_id",
        "resource_request_supports",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("resource_request_supports")
    op.drop_table("resource_requests")
    op.drop_table("resource_dislikes")
    for column in ("year", "grade", "teacher", "major", "college", "resource_type"):
        op.drop_index(f"ix_resources_{column}", table_name="resources")
    for column in (
        "report_count",
        "dislike_count",
        "is_anonymous",
        "year",
        "grade",
        "teacher",
        "major",
        "college",
        "resource_type",
    ):
        op.drop_column("resources", column)
    op.drop_column("users", "onboarding_completed")
