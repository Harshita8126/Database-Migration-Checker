"""
FastAPI Backend Application.
PostgreSQL Database Migration Safety Checker

"""

import uuid
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.database import DBConfig, test_connection, get_readonly_connection
from backend.metadata import (
    TableMetadata,
    fetch_table_metadata,
    create_manual_metadata,
    get_demo_production_metadata,
)
from backend.risk_engine import analyze_migration_sql, AnalysisResult
from backend.safe_sql import generate_safe_migration_script
from backend.report import (
    build_markdown_report,
    build_json_report,
    generate_pipeline_dot,
    generate_decision_tree_dot,
)

app = FastAPI(
    title="PostgreSQL Migration Safety Checker API",
    description="Pre-deployment migration risk analyzer & safe SQL generator",
    version="1.0.0",
)

# Enable CORS for local Streamlit and frontend tooling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for generated reports
REPORTS_CACHE: Dict[str, Dict[str, Any]] = {}


class AnalyzeRequest(BaseModel):
    sql_content: str = Field(..., description="Raw SQL migration content")
    analysis_mode: str = Field(
        default="static_analysis",
        description="'static_analysis', 'database_aware', 'manual_metadata', or 'demo_production'",
    )
    db_config: Optional[DBConfig] = None
    manual_tables: Optional[List[Dict[str, Any]]] = None
    pg_version: int = 150000


@app.get("/")
def read_root():
    return {
        "project": "PostgreSQL Database Migration Safety Checker",
        "status": "online",
        "endpoints": [
            "POST /connect-db",
            "POST /analyze",
            "GET /metadata",
            "GET /demo-metadata",
            "GET /report/{report_id}",
            "GET /flowcharts/pipeline",
            "GET /flowcharts/decision-tree",
        ],
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/connect-db")
def api_test_connection(config: DBConfig):
    """
    Tests database connectivity using a short-lived read-only connection.
    Does NOT execute any migrations. Never leaks database password.
    """
    res = test_connection(config)
    if not res.get("success"):
        return {"status": "error", "details": res}
    return {"status": "connected", "details": res}


@app.get("/demo-metadata")
def api_demo_metadata():
    """Returns realistic mock production table metadata for demoing."""
    data = get_demo_production_metadata()
    return {tbl: m.to_dict() for tbl, m in data.items()}


@app.get("/metadata")
def api_fetch_metadata(
    host: str = "localhost",
    port: int = 5432,
    database: str = "postgres",
    username: str = "postgres",
    password: Optional[str] = None,
    table_name: str = "orders",
):
    """Fetches real-time metadata for a specific table using psycopg3."""
    config = DBConfig(
        host=host, port=port, database=database, username=username, password=password
    )
    conn_res = test_connection(config)
    if not conn_res.get("success"):
        raise HTTPException(status_code=400, detail=conn_res.get("message"))

    try:
        with get_readonly_connection(config) as conn:
            meta = fetch_table_metadata(conn, table_name=table_name)
            return meta.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to query table metadata: {str(exc)}")


@app.post("/analyze")
def api_analyze_migration(request: AnalyzeRequest):
    """
    Full migration risk assessment endpoint.
    Parses SQL with pglast, extracts table metadata (live, manual, or demo),
    runs safety rules, generates safe SQL, and creates report artifacts.
    """
    if not request.sql_content.strip():
        raise HTTPException(status_code=400, detail="SQL content cannot be empty.")

    metadata_map: Dict[str, TableMetadata] = {}
    pg_version = request.pg_version
    version_str = f"PostgreSQL {pg_version // 10000}.0"

    # 1. Fetch metadata based on selected mode
    if request.analysis_mode == "demo_production":
        metadata_map = get_demo_production_metadata()
        version_str = "PostgreSQL 16.2 (Demo Production DB)"
    elif request.analysis_mode == "manual_metadata" and request.manual_tables:
        for t_info in request.manual_tables:
            tbl_name = t_info.get("table_name", "orders")
            rows = int(t_info.get("estimated_rows", 1_000_000))
            size_mb = float(t_info.get("size_mb", 250.0))
            metadata_map[tbl_name] = create_manual_metadata(tbl_name, rows, size_mb)
        version_str = "PostgreSQL (Manual Metadata Mode)"
    elif request.analysis_mode == "database_aware" and request.db_config:
        test_res = test_connection(request.db_config)
        if test_res.get("success"):
            if test_res.get("version_num"):
                pg_version = test_res["version_num"]
            version_str = test_res.get("version", version_str)
            try:
                from backend.parser import parse_sql_migration
                parsed = parse_sql_migration(request.sql_content)
                tables_to_query = {
                    s.table_name for s in parsed.statements if s.table_name
                }
                with get_readonly_connection(request.db_config) as conn:
                    for tbl in tables_to_query:
                        metadata_map[tbl] = fetch_table_metadata(conn, tbl)
            except Exception as e:
                # Fallback to static if live fetch failed
                pass
        else:
            # If DB failed to connect, flag in report
            version_str += " (Connection failed, falling back to static analysis)"

    # 2. Run rule-based risk analysis
    analysis_result = analyze_migration_sql(
        sql_content=request.sql_content,
        metadata_map=metadata_map,
        pg_version=pg_version,
        analysis_mode=request.analysis_mode,
    )

    if not analysis_result.success:
        return {
            "success": False,
            "error": analysis_result.error,
            "error_line": analysis_result.error_line,
        }

    # 3. Generate Safe SQL script
    safe_script_res = generate_safe_migration_script(
        original_sql=request.sql_content,
        issues=analysis_result.issues,
        has_lock_timeout=analysis_result.summary.has_lock_timeout if analysis_result.summary else False,
    )

    # 4. Generate Reports
    md_report = build_markdown_report(analysis_result, db_version_str=version_str)
    json_report = build_json_report(analysis_result, db_version_str=version_str)

    # 5. Cache Report for retrieval
    report_id = str(uuid.uuid4())
    report_bundle = {
        "report_id": report_id,
        "analysis": analysis_result.to_dict(),
        "safe_sql": safe_script_res,
        "markdown_report": md_report,
        "json_report": json_report,
        "version_str": version_str,
    }
    REPORTS_CACHE[report_id] = report_bundle

    return report_bundle


@app.get("/report/{report_id}")
def api_get_report(report_id: str):
    """Retrieves an existing cached analysis report."""
    if report_id not in REPORTS_CACHE:
        raise HTTPException(status_code=404, detail="Report ID not found.")
    return REPORTS_CACHE[report_id]


@app.get("/flowcharts/pipeline")
def api_get_pipeline_flowchart():
    """Returns Graphviz DOT code for the system workflow."""
    return {"dot": generate_pipeline_dot()}


@app.get("/flowcharts/decision-tree")
def api_get_decision_flowchart():
    """Returns Graphviz DOT code for the rule decision tree."""
    return {"dot": generate_decision_tree_dot()}
