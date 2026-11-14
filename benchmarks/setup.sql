-- Setup test database environment for Migration Safety Checker benchmarks
-- Team Load Balancers - Chitkara University (Hacknauts 2.0)

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INT,
    total_amount NUMERIC(10, 2),
    status VARCHAR(50) DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed customers (10,000 records)
INSERT INTO customers (name, email)
SELECT 
    'Customer ' || g,
    'user_' || g || '@example.com'
FROM generate_series(1, 10000) AS g;

-- Seed orders (500,000 records for benchmark testing)
INSERT INTO orders (customer_id, total_amount, status, notes, created_at)
SELECT 
    (1 + (g % 10000)),
    (10.0 + (g % 500) * 1.5)::numeric(10,2),
    CASE (g % 4)
        WHEN 0 THEN 'pending'
        WHEN 1 THEN 'processing'
        WHEN 2 THEN 'completed'
        ELSE 'cancelled'
    END,
    'Order notes for transaction reference ' || g,
    CURRENT_TIMESTAMP - (g || ' seconds')::INTERVAL
FROM generate_series(1, 500000) AS g;

-- Analyze table to update query planner statistics
VACUUM ANALYZE orders;
VACUUM ANALYZE customers;
