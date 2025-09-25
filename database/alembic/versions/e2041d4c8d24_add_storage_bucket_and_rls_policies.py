"""Add storage bucket and RLS policies

Revision ID: [自动生成的ID]
Revises: e9a8254a2dd4
Create Date: [自动生成的时间]

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "[自动生成的ID]"
down_revision = "e9a8254a2dd4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建存储桶
    op.execute(
        """
        INSERT INTO storage.buckets (id, name, public)
        VALUES ('amazon-assets', 'amazon-assets', true)
        ON CONFLICT (id) DO NOTHING;
    """
    )

    # 创建存储策略
    op.execute(
        """
        CREATE POLICY "Public read access" ON storage.objects
        FOR SELECT USING (bucket_id = 'amazon-assets');
    """
    )

    op.execute(
        """
        CREATE POLICY "Service role can insert" ON storage.objects
        FOR INSERT WITH CHECK (bucket_id = 'amazon-assets' AND auth.role() = 'service_role');
    """
    )

    op.execute(
        """
        CREATE POLICY "Service role can update" ON storage.objects
        FOR UPDATE USING (bucket_id = 'amazon-assets' AND auth.role() = 'service_role');
    """
    )

    op.execute(
        """
        CREATE POLICY "Service role can delete" ON storage.objects
        FOR DELETE USING (bucket_id = 'amazon-assets' AND auth.role() = 'service_role');
    """
    )

    # 启用行级安全
    op.execute("ALTER TABLE amazon_products ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE amazon_product_bullets ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE amazon_product_images ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE amazon_product_attributes ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE amazon_html_snapshots ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE scrape_tasks ENABLE ROW LEVEL SECURITY;")

    # 创建公共读策略
    tables = [
        "amazon_products",
        "amazon_product_bullets",
        "amazon_product_images",
        "amazon_product_attributes",
        "amazon_html_snapshots",
        "scrape_tasks",
    ]

    for table in tables:
        op.execute(
            f"""
            CREATE POLICY "Public read access" ON {table}
            FOR SELECT USING (true);
        """
        )

        op.execute(
            f"""
            CREATE POLICY "Service role full access" ON {table}
            FOR ALL USING (auth.role() = 'service_role');
        """
        )


def downgrade() -> None:
    # 删除存储策略
    op.execute('DROP POLICY IF EXISTS "Public read access" ON storage.objects;')
    op.execute('DROP POLICY IF EXISTS "Service role can insert" ON storage.objects;')
    op.execute('DROP POLICY IF EXISTS "Service role can update" ON storage.objects;')
    op.execute('DROP POLICY IF EXISTS "Service role can delete" ON storage.objects;')

    # 删除存储桶
    op.execute("DELETE FROM storage.buckets WHERE id = 'amazon-assets';")

    # 删除表策略
    tables = [
        "amazon_products",
        "amazon_product_bullets",
        "amazon_product_images",
        "amazon_product_attributes",
        "amazon_html_snapshots",
        "scrape_tasks",
    ]

    for table in tables:
        op.execute(f'DROP POLICY IF EXISTS "Public read access" ON {table};')
        op.execute(f'DROP POLICY IF EXISTS "Service role full access" ON {table};')

    # 禁用行级安全
    op.execute("ALTER TABLE amazon_products DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE amazon_product_bullets DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE amazon_product_images DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE amazon_product_attributes DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE amazon_html_snapshots DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE scrape_tasks DISABLE ROW LEVEL SECURITY;")
