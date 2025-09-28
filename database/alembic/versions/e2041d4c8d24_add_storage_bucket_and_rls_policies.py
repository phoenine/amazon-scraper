"""Add storage bucket and RLS policies

Revision ID: e2041d4c8d24
Revises: 696626eef284
Create Date: 2025-09-28 15:38:23.369495

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e2041d4c8d24"
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

    # 创建存储策略 - 先删除可能存在的策略，然后创建新的
    op.execute('DROP POLICY IF EXISTS "Public read access" ON storage.objects;')
    op.execute(
        """
        CREATE POLICY "Public read access" ON storage.objects
        FOR SELECT USING (bucket_id = 'amazon-assets');
    """
    )

    op.execute('DROP POLICY IF EXISTS "Service role can insert" ON storage.objects;')
    op.execute(
        """
        CREATE POLICY "Service role can insert" ON storage.objects
        FOR INSERT WITH CHECK (bucket_id = 'amazon-assets' AND auth.role() = 'service_role');
    """
    )

    op.execute('DROP POLICY IF EXISTS "Service role can update" ON storage.objects;')
    op.execute(
        """
        CREATE POLICY "Service role can update" ON storage.objects
        FOR UPDATE USING (bucket_id = 'amazon-assets' AND auth.role() = 'service_role');
    """
    )

    op.execute('DROP POLICY IF EXISTS "Service role can delete" ON storage.objects;')
    op.execute(
        """
        CREATE POLICY "Service role can delete" ON storage.objects
        FOR DELETE USING (bucket_id = 'amazon-assets' AND auth.role() = 'service_role');
    """
    )

    # 启用行级安全 - 只对实际存在的表
    tables_to_enable_rls = [
        "amazon_products",
        "amazon_product_bullets",
        "amazon_product_images",
        "amazon_aplus_images",
        "amazon_aplus_contents",
        "scrape_tasks",
    ]

    for table in tables_to_enable_rls:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")

    # 创建公共读策略 - 只对实际存在的表
    for table in tables_to_enable_rls:
        # 先删除可能存在的策略
        op.execute(f'DROP POLICY IF EXISTS "Public read access" ON {table};')
        op.execute(f'DROP POLICY IF EXISTS "Service role full access" ON {table};')

        # 创建新策略
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

    # 删除表策略 - 只对实际存在的表
    tables_to_disable_rls = [
        "amazon_products",
        "amazon_product_bullets",
        "amazon_product_images",
        "amazon_aplus_images",
        "amazon_aplus_contents",
        "scrape_tasks",
    ]

    for table in tables_to_disable_rls:
        op.execute(f'DROP POLICY IF EXISTS "Public read access" ON {table};')
        op.execute(f'DROP POLICY IF EXISTS "Service role full access" ON {table};')

    # 禁用行级安全
    for table in tables_to_disable_rls:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
