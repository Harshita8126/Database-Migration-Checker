-- Unsafe E-Commerce Migration Script
-- Contains classic production anti-patterns that cause lock queues and downtime.

-- Step 1: Create index on large orders table without CONCURRENTLY
-- Risk: Acquires SHARE lock, completely blocking all INSERT/UPDATE/DELETE queries
CREATE INDEX idx_orders_customer_id ON orders(customer_id);

-- Step 2: Directly apply SET NOT NULL to an existing column
-- Risk: Sequential scan of entire table under ACCESS EXCLUSIVE lock
ALTER TABLE orders ALTER COLUMN total_amount SET NOT NULL;

-- Step 3: Add foreign key without NOT VALID
-- Risk: Locks referenced table and scans orders table
ALTER TABLE orders ADD CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id);

-- Step 4: Unbounded bulk UPDATE
-- Risk: Heavy row locks, WAL explosion, and replication lag
UPDATE orders SET status = 'archived';

-- Step 5: Expensive column type change
-- Risk: Rewrites entire table on disk under ACCESS EXCLUSIVE lock
ALTER TABLE users ALTER COLUMN phone_number TYPE bigint;
