
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(80) NOT NULL,
    status VARCHAR(10) NOT NULL
        CHECK (status IN ('lost', 'found')),
    location VARCHAR(200) NOT NULL,
    item_date DATE,
    image_url TEXT,
    reporter_name VARCHAR(100) NOT NULL,
    reporter_email VARCHAR(150) NOT NULL,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolution_token_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add the lifecycle flag when upgrading an existing database.
ALTER TABLE items
    ADD COLUMN IF NOT EXISTS is_resolved BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS resolution_token_hash TEXT;
