"""Add team_members table and seat tracking columns

Revision ID: 003_team_seats
Revises: 002_subscriptions
Create Date: 2025-01-20 14:00:00.000000

BREAKING: renames `subscriptions.seats` → `subscriptions.seat_count`
and drops the old `max_seats` column from `products`.
Any code referencing `subscription.seats` or `product.max_seats` must be updated.
"""
from alembic import op
import sqlalchemy as sa

revision = "003_team_seats"
down_revision = "002_subscriptions"
branch_labels = None
depends_on = None


def upgrade():
    # Rename column — BREAKING for any raw SQL or ORM code using old name
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.alter_column("seats", new_column_name="seat_count")

    # Drop deprecated column from products
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_column("max_seats")

    # New team_members table
    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("invited_by_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["invited_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id", "user_id", name="uq_team_member_subscription_user"),
    )
    op.create_index("ix_team_members_subscription_id", "team_members", ["subscription_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])

    # Add seat_used counter to subscriptions
    op.add_column("subscriptions", sa.Column("seats_used", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    op.drop_column("subscriptions", "seats_used")
    op.drop_table("team_members")

    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("max_seats", sa.Integer(), nullable=True))

    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.alter_column("seat_count", new_column_name="seats")
