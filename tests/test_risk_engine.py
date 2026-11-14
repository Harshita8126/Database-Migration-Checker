"""
Unit tests for the Risk Engine and Safe SQL Generator.

"""

from backend.risk_engine import analyze_migration_sql
from backend.safe_sql import generate_safe_migration_script
from backend.metadata import get_demo_production_metadata


def test_missing_lock_timeout_flagged():
    sql = "ALTER TABLE orders ADD COLUMN points int;"
    res = analyze_migration_sql(sql)
    assert res.success is True
    # Should flag missing lock timeout
    rule_names = [i["rule_name"] for i in res.issues]
    assert "Missing lock_timeout Setting" in rule_names


def test_migration_with_lock_timeout_not_flagged():
    sql = """
    SET lock_timeout = '3s';
    CREATE INDEX CONCURRENTLY idx_clean ON orders(id);
    """
    res = analyze_migration_sql(sql)
    assert res.success is True
    assert res.summary.has_lock_timeout is True
    rule_names = [i["rule_name"] for i in res.issues]
    assert "Missing lock_timeout Setting" not in rule_names
    assert res.summary.overall_risk == "LOW"


def test_full_unsafe_migration_analysis():
    sql = """
    CREATE INDEX idx_orders_customer ON orders(customer_id);
    ALTER TABLE orders ALTER COLUMN amount SET NOT NULL;
    UPDATE orders SET status = 'migrated';
    """
    demo_meta = get_demo_production_metadata()
    res = analyze_migration_sql(sql, metadata_map=demo_meta, analysis_mode="demo_production")
    assert res.success is True
    assert res.summary.overall_risk == "HIGH"
    assert res.summary.high_count >= 2

    # Verify safe SQL generation
    safe = generate_safe_migration_script(sql, res.issues, res.summary.has_lock_timeout)
    assert "SET lock_timeout = '3s';" in safe["safe_script"]
    assert "CREATE INDEX CONCURRENTLY" in safe["safe_script"]
    assert "CHECK" in safe["safe_script"]
    assert "NOT VALID" in safe["safe_script"]
