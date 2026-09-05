"""Add resource likes and comments."""

import sqlalchemy as sa
from alembic import op

revision = "20260905_0002"
down_revision = "20260904_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resources",
        sa.Column("like_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "resources",
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "resource_likes",
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
        sa.UniqueConstraint("resource_id", "user_id", name="uq_resource_like"),
    )
    op.create_index("ix_resource_likes_resource_id", "resource_likes", ["resource_id"])
    op.create_index("ix_resource_likes_user_id", "resource_likes", ["user_id"])
    op.create_table(
        "resource_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resource_id",
            sa.String(36),
            sa.ForeignKey("resources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_resource_comments_resource_id", "resource_comments", ["resource_id"]
    )
    op.create_index("ix_resource_comments_author_id", "resource_comments", ["author_id"])


def downgrade() -> None:
    op.drop_table("resource_comments")
    op.drop_table("resource_likes")
    op.drop_column("resources", "comment_count")
    op.drop_column("resources", "like_count")
