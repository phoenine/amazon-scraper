-- Create amazon_aplus_contents table
CREATE TABLE IF NOT EXISTS amazon_aplus_contents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES amazon_products(id) ON DELETE CASCADE,

-- A+ content fields
brand_story TEXT,
faq JSONB,
product_information JSONB,
created_at TIMESTAMPTZ DEFAULT NOW(),
updated_at TIMESTAMPTZ DEFAULT NOW(),

-- Ensure each product has only one A+ content record
UNIQUE(product_id) );

-- Create amazon_aplus_images table
CREATE TABLE IF NOT EXISTS amazon_aplus_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES amazon_products(id) ON DELETE CASCADE,

-- Image basic info (following amazon_product_images pattern)
original_url TEXT NOT NULL,
storage_path TEXT,
width INTEGER,
height INTEGER,
position SMALLINT NOT NULL,

-- A+ specific fields
alt_text TEXT,
image_type TEXT CHECK (
    image_type IN (
        'detail',
        'scene',
        'lifestyle',
        'comparison',
        'infographic'
    )
),
content_section TEXT, -- brand_story, faq, product_info, etc.

-- Status management (simplified)
status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'stored', 'failed')),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for amazon_aplus_contents
CREATE INDEX IF NOT EXISTS idx_amazon_aplus_contents_product_id ON amazon_aplus_contents (product_id);

CREATE INDEX IF NOT EXISTS idx_amazon_aplus_contents_updated_at ON amazon_aplus_contents (updated_at);

-- Create indexes for amazon_aplus_images
CREATE INDEX IF NOT EXISTS idx_amazon_aplus_images_product_id ON amazon_aplus_images (product_id);

CREATE INDEX IF NOT EXISTS idx_amazon_aplus_images_section ON amazon_aplus_images (product_id, content_section);

CREATE INDEX IF NOT EXISTS idx_amazon_aplus_images_type ON amazon_aplus_images (image_type);

CREATE INDEX IF NOT EXISTS idx_amazon_aplus_images_status ON amazon_aplus_images (status);

-- Create trigger for updated_at on amazon_aplus_contents
CREATE TRIGGER update_amazon_aplus_contents_updated_at
    BEFORE UPDATE ON amazon_aplus_contents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();