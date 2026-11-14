"""
Integration tests for FastAPI endpoints.

"""

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_api_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


def test_api_demo_metadata():
    res = client.get("/demo-metadata")
    assert res.status_code == 200
    data = res.json()
    assert "orders" in data
    assert data["orders"]["estimated_rows"] > 10_000_000


def test_api_analyze_unsafe_migration():
    sql = """
    CREATE INDEX idx_orders_amt ON orders(amount);
    ALTER TABLE orders ALTER COLUMN status SET NOT NULL;
    """
    res = client.post("/analyze", json={"sql_content": sql, "analysis_mode": "demo_production"})
    assert res.status_code == 200
    body = res.json()
    assert body["analysis"]["summary"]["overall_risk"] == "HIGH"
    assert len(body["analysis"]["issues"]) >= 2
    assert "safe_script" in body["safe_sql"]
    assert "CONCURRENTLY" in body["safe_sql"]["safe_script"]


def test_api_flowcharts():
    res1 = client.get("/flowcharts/pipeline")
    assert res1.status_code == 200
    assert "digraph MigrationPipeline" in res1.json()["dot"]

    res2 = client.get("/flowcharts/decision-tree")
    assert res2.status_code == 200
    assert "digraph RuleDecisionTree" in res2.json()["dot"]
