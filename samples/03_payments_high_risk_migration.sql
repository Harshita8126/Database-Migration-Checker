-- High-Risk Payments Migration
-- Destructive schema alterations and volatile column defaults.

-- Step 1: Add column with volatile default function (forces full table rewrite even on PG11+)
ALTER TABLE payments ADD COLUMN transaction_token uuid DEFAULT gen_random_uuid() NOT NULL;

-- Step 2: Destructive table drop (immediate permanent loss)
DROP TABLE old_audit_logs;
