-- Create amazon_products table 当前使用alembic，不用这个
CREATE TABLE IF NOT EXISTS amazon_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asin TEXT NOT NULL,
    marketplace TEXT NOT NULL,
    title TEXT,
    rating NUMERIC(3,2),
    ratings_count INTEGER,
    price_amount NUMERIC(12,2),
    price_currency TEXT,
    hero_image_url TEXT,
    hero_image_path TEXT,
    availability TEXT,
    best_sellers_rank JSONB,
    raw_html_snapshot_id UUID,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('fresh', 'stale', 'failed', 'pending')),
    etag TEXT,
    last_scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(asin, marketplace)
);

-- Create amazon_product_bullets table
CREATE TABLE IF NOT EXISTS amazon_product_bullets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES amazon_products(id) ON DELETE CASCADE,
    position SMALLINT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create amazon_product_images table
CREATE TABLE IF NOT EXISTS amazon_product_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES amazon_products(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('hero', 'gallery')),
    original_url TEXT NOT NULL,
    storage_path TEXT,
    width INTEGER,
    height INTEGER,
    position SMALLINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create amazon_product_attributes table
CREATE TABLE IF NOT EXISTS amazon_product_attributes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES amazon_products(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('tech_details', 'product_information')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create amazon_html_snapshots table
CREATE TABLE IF NOT EXISTS amazon_html_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asin TEXT NOT NULL,
    marketplace TEXT NOT NULL,
    html TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create scrape_tasks table
CREATE TABLE IF NOT EXISTS scrape_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asin TEXT NOT NULL,
    marketplace TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'success', 'failed')),
    error TEXT,
    requested_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_amazon_products_asin_marketplace ON amazon_products(asin, marketplace);
CREATE INDEX IF NOT EXISTS idx_amazon_products_last_scraped_at ON amazon_products(last_scraped_at);
CREATE INDEX IF NOT EXISTS idx_amazon_products_status ON amazon_products(status);
CREATE INDEX IF NOT EXISTS idx_amazon_products_best_sellers_rank ON amazon_products USING GIN(best_sellers_rank);

CREATE INDEX IF NOT EXISTS idx_amazon_product_bullets_product_id ON amazon_product_bullets(product_id);
CREATE INDEX IF NOT EXISTS idx_amazon_product_bullets_position ON amazon_product_bullets(product_id, position);

CREATE INDEX IF NOT EXISTS idx_amazon_product_images_product_id ON amazon_product_images(product_id);
CREATE INDEX IF NOT EXISTS idx_amazon_product_images_role ON amazon_product_images(product_id, role);

CREATE INDEX IF NOT EXISTS idx_amazon_product_attributes_product_id ON amazon_product_attributes(product_id);
CREATE INDEX IF NOT EXISTS idx_amazon_product_attributes_source ON amazon_product_attributes(product_id, source);

CREATE INDEX IF NOT EXISTS idx_scrape_tasks_status ON scrape_tasks(status);
CREATE INDEX IF NOT EXISTS idx_scrape_tasks_asin_marketplace ON scrape_tasks(asin, marketplace);
CREATE INDEX IF NOT EXISTS idx_scrape_tasks_created_at ON scrape_tasks(created_at);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_amazon_products_updated_at BEFORE UPDATE ON amazon_products FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_amazon_html_snapshots_updated_at BEFORE UPDATE ON amazon_html_snapshots FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_scrape_tasks_updated_at BEFORE UPDATE ON scrape_tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();