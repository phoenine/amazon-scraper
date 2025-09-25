-- Enable Row Level Security
ALTER TABLE amazon_products ENABLE ROW LEVEL SECURITY;

ALTER TABLE amazon_product_bullets ENABLE ROW LEVEL SECURITY;

ALTER TABLE amazon_product_images ENABLE ROW LEVEL SECURITY;

ALTER TABLE amazon_product_attributes ENABLE ROW LEVEL SECURITY;

ALTER TABLE amazon_html_snapshots ENABLE ROW LEVEL SECURITY;

ALTER TABLE scrape_tasks ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for read access (public)
CREATE POLICY "Allow public read access" ON amazon_products FOR
SELECT USING (true);

CREATE POLICY "Allow public read access" ON amazon_product_bullets FOR
SELECT USING (true);

CREATE POLICY "Allow public read access" ON amazon_product_images FOR
SELECT USING (true);

CREATE POLICY "Allow public read access" ON amazon_product_attributes FOR
SELECT USING (true);

CREATE POLICY "Allow public read access" ON scrape_tasks FOR
SELECT USING (true);

-- Create RLS policies for write access (service role only)
CREATE POLICY "Allow service role write access" ON amazon_products FOR ALL USING (auth.role () = 'service_role');

CREATE POLICY "Allow service role write access" ON amazon_product_bullets FOR ALL USING (auth.role () = 'service_role');

CREATE POLICY "Allow service role write access" ON amazon_product_images FOR ALL USING (auth.role () = 'service_role');

CREATE POLICY "Allow service role write access" ON amazon_product_attributes FOR ALL USING (auth.role () = 'service_role');

CREATE POLICY "Allow service role write access" ON amazon_html_snapshots FOR ALL USING (auth.role () = 'service_role');

CREATE POLICY "Allow service role write access" ON scrape_tasks FOR ALL USING (auth.role () = 'service_role');