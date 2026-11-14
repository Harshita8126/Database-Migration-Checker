"""
Migration Safety Rule: Constraint Rules (SET NOT NULL and ADD FOREIGN KEY).
Calibrated directly against real benchmark datasets:
- benchmarks/migration_dataset_v3.csv (Execution & lock duration on 1K, 10K, 100K, 1M rows)
- benchmarks/performance_dataset_v2.csv (Latency spikes & TPS degradation under concurrent workload)
"""

from typing import List, Dict, Any, Optional
from backend.parser import ParsedStatement
from backend.metadata import TableMetadata
from backend.rules.dataset_calibration import BENCHMARK_MODEL


def check_constraint_rules(
    stmt: ParsedStatement,
    metadata_map: Dict[str, TableMetadata],
    pg_version: int = 150000
) -> List[Dict[str, Any]]:
    """
    Analyzes ALTER TABLE statements adding constraints or setting columns NOT NULL.
    Calibrated directly with empirical benchmarks.
    """
    issues = []
    if stmt.statement_type != "ALTER TABLE":
        return issues

    table_name = stmt.table_name or "unknown_table"
    commands = stmt.details.get("commands", [])
    meta = metadata_map.get(table_name)
    rows = meta.estimated_rows if meta else 0
    size_bytes = meta.total_size_bytes if meta else 0
    size_str = meta.total_size_pretty if meta else "unknown size"

    emp_con = BENCHMARK_MODEL.get_empirical_metrics("ADD CONSTRAINT", rows, size_bytes)
    measured_con_sec = emp_con["measured_exec_sec"]
    severity_con = emp_con["severity"]

    for cmd in commands:
        cmd_type = cmd.get("type")

        # -------------------------------------------------------------
        # Rule 3: SET NOT NULL
        # -------------------------------------------------------------
        if cmd_type == "SET_NOT_NULL":
            col_name = cmd.get("column", "column_name")
            con_name = f"chk_{table_name}_{col_name}_not_null"

            safe_sql = (
                f"-- Step 1: Add CHECK constraint with NOT VALID (instant metadata lock)\n"
                f"ALTER TABLE {table_name}\n"
                f"ADD CONSTRAINT {con_name}\n"
                f"CHECK ({col_name} IS NOT NULL) NOT VALID;\n\n"
                f"-- Step 2: Validate in background (non-blocking scan)\n"
                f"ALTER TABLE {table_name}\n"
                f"VALIDATE CONSTRAINT {con_name};\n\n"
                f"-- Step 3 (PostgreSQL 12+): Safe instant SET NOT NULL\n"
                f"ALTER TABLE {table_name}\n"
                f"ALTER COLUMN {col_name} SET NOT NULL;"
            )

            issues.append({
                "rule_name": "Direct SET NOT NULL on Table",
                "severity": severity_con,
                "table": table_name,
                "line_number": stmt.line_number,
                "reason": (
                    f"ALTER TABLE ... SET NOT NULL requires an ACCESS EXCLUSIVE lock while scanning every row "
                    f"in '{table_name}' to verify nullability."
                ),
                "impact": (
                    f"Scans ~{rows:,} rows under exclusive lock hold (measured benchmark duration: {measured_con_sec:.3f}s), "
                    f"blocking all concurrent queries on '{table_name}'."
                ),
                "suggestion": "Add a CHECK (col IS NOT NULL) NOT VALID constraint first, validate it asynchronously, then apply SET NOT NULL.",
                "doc_url": "https://www.postgresql.org/docs/current/sql-altertable.html#SQL-ALTERTABLE-NOTES",
                "safe_sql": safe_sql,
                "original_sql": stmt.raw_sql,
                "operation": f"ALTER COLUMN {col_name} SET NOT NULL",
                "lock_level": "ACCESS EXCLUSIVE (Table scan)",
                "estimated_lock_risk": f"Empirical CSV benchmark: {measured_con_sec:.3f}s lock hold",
            })

        # -------------------------------------------------------------
        # Rule 4: ADD FOREIGN KEY / ADD CONSTRAINT without NOT VALID
        # -------------------------------------------------------------
        elif cmd_type in ["ADD_FOREIGN_KEY", "ADD_CONSTRAINT"]:
            con_name = cmd.get("constraint_name") or f"fk_{table_name}_ref"
            is_fk = cmd_type == "ADD_FOREIGN_KEY" or "FOREIGN KEY" in stmt.raw_sql.upper()
            is_not_valid = cmd.get("not_valid", False) or "NOT VALID" in stmt.raw_sql.upper()
            ref_table = cmd.get("foreign_table") or "referenced_table"

            if not is_not_valid:
                raw_upper = stmt.raw_sql.strip()
                cleaned_semi = raw_upper.rstrip(";")
                safe_add = f"{cleaned_semi} NOT VALID;\n"
                safe_validate = f"ALTER TABLE {table_name} VALIDATE CONSTRAINT {con_name};"
                safe_sql = f"{safe_add}{safe_validate}"

                rule_title = "Unvalidated ADD FOREIGN KEY" if is_fk else "Adding Constraint without NOT VALID"

                issues.append({
                    "rule_name": rule_title,
                    "severity": severity_con,
                    "table": table_name,
                    "line_number": stmt.line_number,
                    "reason": (
                        f"Adding constraint '{con_name}' without 'NOT VALID' immediately scans the entire table "
                        f"under a SHARE ROW EXCLUSIVE lock"
                        + (f" and locks referenced table '{ref_table}'." if is_fk else ".")
                    ),
                    "impact": (
                        f"Blocks write operations on '{table_name}' (~{rows:,} rows, {size_str}) during the "
                        f"entire sequential scan (measured benchmark duration: {measured_con_sec:.3f}s)."
                    ),
                    "suggestion": "Create the constraint with 'NOT VALID' (fast metadata lock), then run 'VALIDATE CONSTRAINT' in a separate transaction.",
                    "doc_url": "https://www.postgresql.org/docs/current/sql-altertable.html",
                    "safe_sql": safe_sql,
                    "original_sql": stmt.raw_sql,
                    "operation": f"ADD CONSTRAINT {con_name}",
                    "lock_level": "SHARE ROW EXCLUSIVE",
                    "estimated_lock_risk": f"Empirical CSV benchmark: {measured_con_sec:.3f}s lock hold",
                })

    return issues
