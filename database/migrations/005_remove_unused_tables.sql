-- Remove unused tables and fields
-- This migration removes amazon_product_attributes, amazon_html_snapshots tables
-- and availability field from amazon_products table

-- Drop amazon_product_attributes table
DROP TABLE IF EXISTS amazon_product_attributes CASCADE;

-- Drop amazon_html_snapshots table
DROP TABLE IF EXISTS amazon_html_snapshots CASCADE;

-- Remove availability column from amazon_products table
ALTER TABLE amazon_products DROP COLUMN IF EXISTS availability;

-- Remove raw_html_snapshot_id column from amazon_products table (if exists)
ALTER TABLE amazon_products
DROP COLUMN IF EXISTS raw_html_snapshot_id;

-- Update updated_at trigger to reflect the changes
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Ensure the trigger exists for amazon_products
DROP TRIGGER IF EXISTS update_amazon_products_updated_at ON amazon_products;

CREATE TRIGGER update_amazon_products_updated_at
    BEFORE UPDATE ON amazon_products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Ensure the trigger exists for amazon_aplus_contents
DROP TRIGGER IF EXISTS update_amazon_aplus_contents_updated_at ON amazon_aplus_contents;

CREATE TRIGGER update_amazon_aplus_contents_updated_at
    BEFORE UPDATE ON amazon_aplus_contents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();