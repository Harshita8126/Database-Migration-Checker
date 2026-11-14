"""
Unit tests for the SQL AST Parser (pglast).

"""

import pytest
from backend.parser import parse_sql_migration


def test_parse_create_index_non_concurrent():
    sql = "CREATE INDEX idx_orders_amount ON orders(amount);"
    res = parse_sql_migration(sql)
    assert res.success is True
    assert res.total_statements == 1
    stmt = res.statements[0]
    assert stmt.statement_type == "CREATE INDEX"
    assert stmt.table_name == "orders"
    assert stmt.details["concurrent"] is False
    assert stmt.details["index_name"] == "idx_orders_amount"
    assert stmt.line_number == 1


def test_parse_create_index_concurrent():
    sql = "CREATE INDEX CONCURRENTLY idx_orders_amount ON orders(amount);"
    res = parse_sql_migration(sql)
    assert res.success is True
    assert res.statements[0].details["concurrent"] is True


def test_parse_alter_column_type():
    sql = "ALTER TABLE users ALTER COLUMN phone TYPE varchar(20);"
    res = parse_sql_migration(sql)
    assert res.success is True
    stmt = res.statements[0]
    assert stmt.statement_type == "ALTER TABLE"
    assert stmt.table_name == "users"
    cmd = stmt.details["commands"][0]
    assert cmd["type"] == "ALTER_COLUMN_TYPE"
    assert cmd["column"] == "phone"
    assert "varchar" in cmd["new_type"]


def test_parse_set_not_null():
    sql = "ALTER TABLE orders ALTER COLUMN status SET NOT NULL;"
    res = parse_sql_migration(sql)
    assert res.success is True
    cmd = res.statements[0].details["commands"][0]
    assert cmd["type"] == "SET_NOT_NULL"
    assert cmd["column"] == "status"


def test_parse_add_foreign_key_with_and_without_not_valid():
    sql1 = "ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);"
    res1 = parse_sql_migration(sql1)
    assert res1.statements[0].details["commands"][0]["skip_validation"] is False

    sql2 = "ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;"
    res2 = parse_sql_migration(sql2)
    assert res2.statements[0].details["commands"][0]["skip_validation"] is True


def test_parse_update_unbounded_and_bounded():
    sql = """
    UPDATE orders SET status = 'archived';
    UPDATE orders SET status = 'archived' WHERE created_at < NOW() - INTERVAL '1 year';
    """
    res = parse_sql_migration(sql)
    assert res.total_statements == 2
    assert res.statements[0].details["has_where"] is False
    assert res.statements[1].details["has_where"] is True


def test_parse_lock_timeout_detection():
    sql = """
    SET lock_timeout = '3s';
    ALTER TABLE orders ADD COLUMN notes text;
    """
    res = parse_sql_migration(sql)
    assert res.has_lock_timeout is True
    assert res.lock_timeout_value == '3s'


def test_parse_syntax_error_handling():
    sql = "ALTER TABLE orders ADD COLUMN ;;; SYNTAX INVALID"
    res = parse_sql_migration(sql)
    assert res.success is False
    assert "SQL Parsing Error" in res.error
