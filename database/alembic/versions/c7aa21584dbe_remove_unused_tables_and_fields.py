"""Remove unused tables and fields

Revision ID: remove_unused_001
Revises: 38b233e71c9a
Create Date: 2024-01-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "remove_unused_001"
down_revision = "38b233e71c9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove unused tables and fields"""

    # Drop amazon_product_attributes table if it exists
    op.execute("DROP TABLE IF EXISTS amazon_product_attributes CASCADE")

    # Drop amazon_html_snapshots table if it exists
    op.execute("DROP TABLE IF EXISTS amazon_html_snapshots CASCADE")

    # Remove availability column from amazon_products table if it exists
    try:
        op.drop_column("amazon_products", "availability")
    except Exception:
        # Column might not exist, ignore error
        pass

    # Remove raw_html_snapshot_id column from amazon_products table if it exists
    try:
        op.drop_column("amazon_products", "raw_html_snapshot_id")
    except Exception:
        # Column might not exist, ignore error
        pass


def downgrade() -> None:
    """Recreate the removed tables and fields"""

    # Recreate amazon_product_attributes table
    op.create_table(
        "amazon_product_attributes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["amazon_products.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Recreate amazon_html_snapshots table
    op.create_table(
        "amazon_html_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("asin", sa.String(), nullable=False),
        sa.Column("marketplace", sa.String(), nullable=False),
        sa.Column("raw_html", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add back availability column
    op.add_column(
        "amazon_products", sa.Column("availability", sa.Text(), nullable=True)
    )

    # Add back raw_html_snapshot_id column
    op.add_column(
        "amazon_products", sa.Column("raw_html_snapshot_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        None,
        "amazon_products",
        "amazon_html_snapshots",
        ["raw_html_snapshot_id"],
        ["id"],
    )
