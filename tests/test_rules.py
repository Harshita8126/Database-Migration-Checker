"""
Unit tests for Migration Safety Rules.

"""

from backend.parser import parse_sql_migration
from backend.metadata import TableMetadata
from backend.rules.index_rules import check_index_rules
from backend.rules.alter_rules import check_alter_rules
from backend.rules.constraint_rules import check_constraint_rules
from backend.rules.update_rules import check_update_rules


def test_index_rule_flags_non_concurrent():
    sql = "CREATE INDEX idx_orders_amount ON orders(amount);"
    parsed = parse_sql_migration(sql)
    meta = {
        "orders": TableMetadata(
            table_name="orders", estimated_rows=500_000, total_size_pretty="180 MB"
        )
    }
    issues = check_index_rules(parsed.statements[0], meta)
    assert len(issues) == 1
    assert issues[0]["rule_name"] == "Non-Concurrent Index Creation"
    assert issues[0]["severity"] == "HIGH"
    assert "CONCURRENTLY" in issues[0]["safe_sql"]


def test_index_rule_passes_concurrent():
    sql = "CREATE INDEX CONCURRENTLY idx_orders_amount ON orders(amount);"
    parsed = parse_sql_migration(sql)
    issues = check_index_rules(parsed.statements[0], {})
    assert len(issues) == 0


def test_alter_column_type_rule():
    sql = "ALTER TABLE users ALTER COLUMN age TYPE bigint;"
    parsed = parse_sql_migration(sql)
    meta = {
        "users": TableMetadata(table_name="users", estimated_rows=2_000_000, total_size_pretty="500 MB")
    }
    issues = check_alter_rules(parsed.statements[0], meta)
    assert len(issues) == 1
    assert issues[0]["rule_name"] == "Potentially Expensive ALTER COLUMN TYPE"
    assert "Expand-Contract" in issues[0]["suggestion"]


def test_set_not_null_rule():
    sql = "ALTER TABLE orders ALTER COLUMN status SET NOT NULL;"
    parsed = parse_sql_migration(sql)
    issues = check_constraint_rules(parsed.statements[0], {})
    assert len(issues) == 1
    assert issues[0]["rule_name"] == "Direct SET NOT NULL on Table"
    assert "CHECK" in issues[0]["safe_sql"]
    assert "NOT VALID" in issues[0]["safe_sql"]
    assert "VALIDATE CONSTRAINT" in issues[0]["safe_sql"]


def test_add_foreign_key_rule():
    sql = "ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);"
    parsed = parse_sql_migration(sql)
    issues = check_constraint_rules(parsed.statements[0], {})
    assert len(issues) == 1
    assert issues[0]["rule_name"] == "Unvalidated ADD FOREIGN KEY"
    assert "NOT VALID" in issues[0]["safe_sql"]
    assert "VALIDATE CONSTRAINT" in issues[0]["safe_sql"]


def test_unbounded_update_rule():
    sql = "UPDATE orders SET status = 'completed';"
    parsed = parse_sql_migration(sql)
    meta = {"orders": TableMetadata(table_name="orders", estimated_rows=100_000)}
    issues = check_update_rules(parsed.statements[0], meta)
    assert len(issues) == 1
    assert issues[0]["rule_name"] == "Unbounded Table UPDATE"
    assert "LIMIT 5000" in issues[0]["safe_sql"]


def test_drop_table_rule():
    sql = "DROP TABLE old_records;"
    parsed = parse_sql_migration(sql)
    issues = check_update_rules(parsed.statements[0], {})
    assert len(issues) == 1
    assert "DROP TABLE" in issues[0]["rule_name"]
    assert issues[0]["severity"] == "HIGH"
