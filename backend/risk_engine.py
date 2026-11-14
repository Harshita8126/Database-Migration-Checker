"""
Rule-Based Risk Assessment Engine.


Combines:
1. SQL AST information from pglast
2. PostgreSQL metadata from psycopg3 (or manual/demo metadata)
3. PostgreSQL version & lock behavior
4. Modular migration safety rules

Produces a structured, severity-graded risk assessment.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
from backend.parser import parse_sql_migration, ParseResult
from backend.metadata import TableMetadata
from backend.rules.index_rules import check_index_rules
from backend.rules.alter_rules import check_alter_rules
from backend.rules.constraint_rules import check_constraint_rules
from backend.rules.update_rules import check_update_rules
from backend.interpolation import estimate_time, scaling_factor

# Load benchmark dataset for performance time interpolation
_BENCHMARK_CSV_PATH = Path(__file__).resolve().parent.parent / "benchmarks" / "migration_dataset_v3.csv"
_BENCHMARK_DF: Optional[pd.DataFrame] = None
try:
    if _BENCHMARK_CSV_PATH.exists():
        _BENCHMARK_DF = pd.read_csv(_BENCHMARK_CSV_PATH)
except Exception:
    _BENCHMARK_DF = None


@dataclass
class RiskSummary:
    overall_risk: str  # "HIGH", "MEDIUM", "LOW"
    total_statements: int
    total_issues: int
    high_count: int
    medium_count: int
    low_count: int
    has_lock_timeout: bool
    analysis_mode: str  # "database_aware", "manual_metadata", "static_analysis"


@dataclass
class AnalysisResult:
    success: bool
    summary: Optional[RiskSummary] = None
    issues: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_sql: str = ""
    error: Optional[str] = None
    error_line: Optional[int] = None
    performance_estimate: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "summary": asdict(self.summary) if self.summary else None,
            "issues": self.issues,
            "metadata": self.metadata,
            "original_sql": self.original_sql,
            "error": self.error,
            "error_line": self.error_line,
            "performance_estimate": self.performance_estimate,
        }


def analyze_migration_sql(
    sql_content: str,
    metadata_map: Optional[Dict[str, TableMetadata]] = None,
    pg_version: int = 150000,
    analysis_mode: str = "static_analysis"
) -> AnalysisResult:
    """
    Analyzes uploaded SQL migration content using AST parsing and metadata rules.
    """
    if metadata_map is None:
        metadata_map = {}

    parse_res = parse_sql_migration(sql_content)
    if not parse_res.success:
        return AnalysisResult(
            success=False,
            error=parse_res.error,
            error_line=parse_res.error_line,
            original_sql=sql_content
        )

    issues: List[Dict[str, Any]] = []

    # -------------------------------------------------------------
    # Rule 7: Missing lock_timeout (File-level safety check)
    # -------------------------------------------------------------
    has_dangerous_stmts = any(
        s.statement_type in ["ALTER TABLE", "CREATE INDEX", "UPDATE"] or s.statement_type.startswith("DROP")
        for s in parse_res.statements
    )

    if not parse_res.has_lock_timeout and has_dangerous_stmts:
        issues.append({
            "rule_name": "Missing lock_timeout Setting",
            "severity": "HIGH" if any(s.statement_type in ["ALTER TABLE", "DROP TABLE"] for s in parse_res.statements) else "MEDIUM",
            "table": None,
            "line_number": 1,
            "reason": (
                "Migration omits 'SET lock_timeout'. Unacquired locks block behind slow transactions and create lock queues."
            ),
            "impact": "Exhausts database connection pools and causes application-wide request timeouts.",
            "suggestion": "Prepend 'SET lock_timeout = '3s';' and 'SET statement_timeout = '30s';' at the top of the script.",
            "doc_url": "https://www.postgresql.org/docs/current/runtime-config-client.html#GUC-LOCK-TIMEOUT",
            "safe_sql": "SET lock_timeout = '3s';\nSET statement_timeout = '30s';\n",
            "original_sql": "-- (Missing at beginning of script)",
            "operation": "SET lock_timeout",
            "lock_level": "N/A (Lock Queue Guard)",
            "estimated_lock_risk": "Vulnerable to lock convoy",
        })

    # -------------------------------------------------------------
    # Per-Statement Rule Evaluation
    # -------------------------------------------------------------
    for stmt in parse_res.statements:
        # 1. Index rules
        issues.extend(check_index_rules(stmt, metadata_map, pg_version))
        # 2. Alter rules
        issues.extend(check_alter_rules(stmt, metadata_map, pg_version))
        # 3. Constraint rules
        issues.extend(check_constraint_rules(stmt, metadata_map, pg_version))
        # 4. Update / Drop rules
        issues.extend(check_update_rules(stmt, metadata_map, pg_version))

    # Count issues by severity
    high_count = sum(1 for i in issues if i.get("severity") == "HIGH")
    medium_count = sum(1 for i in issues if i.get("severity") == "MEDIUM")
    low_count = sum(1 for i in issues if i.get("severity") == "LOW")

    if high_count > 0:
        overall_risk = "HIGH"
    elif medium_count > 0:
        overall_risk = "MEDIUM"
    else:
        overall_risk = "LOW"

    # Format table metadata for report output
    meta_dict = {tbl: m.to_dict() for tbl, m in metadata_map.items()}

    summary = RiskSummary(
        overall_risk=overall_risk,
        total_statements=parse_res.total_statements,
        total_issues=len(issues),
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        has_lock_timeout=parse_res.has_lock_timeout,
        analysis_mode=analysis_mode,
    )

    # -------------------------------------------------------------
    # Performance Duration Interpolation (Indicative Reference Only)
    # -------------------------------------------------------------
    performance_estimate = None
    if _BENCHMARK_DF is not None and not _BENCHMARK_DF.empty:
        # Identify the primary statement and operation
        primary_stmt = None
        for s in parse_res.statements:
            if s.statement_type in ["CREATE INDEX", "ALTER TABLE", "UPDATE", "DELETE", "DROP TABLE"]:
                primary_stmt = s
                break
        if not primary_stmt and parse_res.statements:
            primary_stmt = parse_res.statements[0]

        if primary_stmt:
            # Map statement type to benchmark operation name
            stmt_t = primary_stmt.statement_type
            op_name = stmt_t
            if stmt_t == "CREATE INDEX":
                op_name = "CREATE INDEX"
            elif stmt_t == "ALTER TABLE":
                cmds = primary_stmt.details.get("commands", [])
                sub_t = cmds[0].get("type") if cmds else ""
                if sub_t == "ALTER_TYPE":
                    op_name = "ALTER COLUMN TYPE"
                elif sub_t == "ADD_COLUMN":
                    op_name = "ADD COLUMN"
                elif sub_t == "ADD_CONSTRAINT":
                    op_name = "ADD CONSTRAINT"
                elif sub_t == "DROP_COLUMN":
                    op_name = "DROP COLUMN"
                else:
                    op_name = "ALTER COLUMN TYPE"

            # Determine table row count from collected metadata
            target_tbl = primary_stmt.table_name
            target_meta = metadata_map.get(target_tbl) if target_tbl else None
            user_rows = target_meta.estimated_rows if target_meta else 0

            # If user_rows is available, run interpolation
            if user_rows and user_rows > 0:
                est_res = estimate_time(
                    df=_BENCHMARK_DF,
                    operation=op_name,
                    user_rows=user_rows,
                    op_col="operation",
                    row_col="row_count",
                    time_col="execution_time_sec",
                    time_is_seconds=True
                )
                sc_info = scaling_factor(
                    df=_BENCHMARK_DF,
                    operation=op_name,
                    op_col="operation",
                    row_col="row_count",
                    time_col="execution_time_sec",
                    time_is_seconds=True
                )
                performance_estimate = {
                    "operation": op_name,
                    "target_table": target_tbl,
                    "user_rows": user_rows,
                    "estimation": est_res,
                    "scaling": sc_info,
                }

    return AnalysisResult(
        success=True,
        summary=summary,
        issues=issues,
        metadata=meta_dict,
        original_sql=sql_content,
        performance_estimate=performance_estimate,
    )
