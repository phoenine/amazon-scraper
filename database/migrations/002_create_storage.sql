-- Create storage bucket for Amazon assets
INSERT INTO
    storage.buckets (id, name, public)
VALUES (
        'amazon-assets',
        'amazon-assets',
        true
    ) ON CONFLICT (id) DO NOTHING;

-- Create storage policies
CREATE POLICY "Allow public read access" ON storage.objects FOR
SELECT USING (bucket_id = 'amazon-assets');

CREATE POLICY "Allow service role write access" ON storage.objects FOR
INSERT
WITH
    CHECK (bucket_id = 'amazon-assets');

CREATE POLICY "Allow service role update access" ON storage.objects FOR
UPDATE USING (bucket_id = 'amazon-assets');

CREATE POLICY "Allow service role delete access" ON storage.objects FOR DELETE USING (bucket_id = 'amazon-assets');