-- Safe E-Commerce Migration Script
-- Production-ready patterns that preserve high availability and prevent downtime.

-- Guardrail 1: Fail fast if lock cannot be acquired immediately
SET lock_timeout = '3s';
SET statement_timeout = '30s';

-- Step 1: Create index CONCURRENTLY (reads & writes continue uninterrupted)
CREATE INDEX CONCURRENTLY idx_orders_customer_id ON orders(customer_id);

-- Step 2: Add CHECK constraint with NOT VALID first (instant metadata lock)
ALTER TABLE orders ADD CONSTRAINT chk_total_amount_not_null CHECK (total_amount IS NOT NULL) NOT VALID;

-- Step 3: Validate constraint in background without blocking write traffic
ALTER TABLE orders VALIDATE CONSTRAINT chk_total_amount_not_null;

-- Step 4: Add foreign key with NOT VALID
ALTER TABLE orders ADD CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id) NOT VALID;

-- Step 5: Validate foreign key constraint in background
ALTER TABLE orders VALIDATE CONSTRAINT fk_orders_customer;
