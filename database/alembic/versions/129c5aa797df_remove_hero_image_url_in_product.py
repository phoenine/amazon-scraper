"""remove_hero_image_url_in_product

Revision ID: 129c5aa797df
Revises: d8f3c2a1b5e7
Create Date: 2025-09-26 15:59:29.485653

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d8f3c2a1b5e7"
down_revision = "remove_unused_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove hero_image_url and hero_image_path columns from amazon_products table"""

    # Remove hero_image_url column from amazon_products table if it exists
    try:
        op.drop_column("amazon_products", "hero_image_url")
        print("✓ Dropped hero_image_url column from amazon_products")
    except Exception as e:
        print(f"⚠ Could not drop hero_image_url column: {e}")

    # Remove hero_image_path column from amazon_products table if it exists
    try:
        op.drop_column("amazon_products", "hero_image_path")
        print("✓ Dropped hero_image_path column from amazon_products")
    except Exception as e:
        print(f"⚠ Could not drop hero_image_path column: {e}")


def downgrade() -> None:
    """Add back hero_image_url and hero_image_path columns to amazon_products table"""

    # Add back hero_image_url column
    try:
        op.add_column(
            "amazon_products", sa.Column("hero_image_url", sa.Text(), nullable=True)
        )
        print("✓ Added back hero_image_url column to amazon_products")
    except Exception as e:
        print(f"⚠ Could not add back hero_image_url column: {e}")

    # Add back hero_image_path column
    try:
        op.add_column(
            "amazon_products", sa.Column("hero_image_path", sa.Text(), nullable=True)
        )
        print("✓ Added back hero_image_path column to amazon_products")
    except Exception as e:
        print(f"⚠ Could not add back hero_image_path column: {e}")
