"""
Migration Safety Rule: ALTER TABLE Rules (Column Type Changes & Column Additions).
Calibrated directly against real benchmark datasets:
- benchmarks/migration_dataset_v3.csv (Execution & lock duration on 1K, 10K, 100K, 1M rows)
- benchmarks/performance_dataset_v2.csv (Latency spikes & TPS degradation under concurrent workload)
"""

from typing import List, Dict, Any, Optional
from backend.parser import ParsedStatement
from backend.metadata import TableMetadata
from backend.rules.dataset_calibration import BENCHMARK_MODEL


def _is_safe_type_change(old_type: Optional[str], new_type: str, pg_version: int) -> bool:
    """
    Checks if a type change can be performed without a table rewrite in modern PostgreSQL.
    """
    clean_new = new_type.lower().strip()
    if not old_type:
        if "bigint" in clean_new or "int8" in clean_new or "timestamp" in clean_new:
            return False
        return False
    clean_old = old_type.lower().strip()

    if clean_old.startswith("varchar") and (clean_new.startswith("varchar") or clean_new == "text"):
        return True
    return False


def check_alter_rules(
    stmt: ParsedStatement,
    metadata_map: Dict[str, TableMetadata],
    pg_version: int = 150000
) -> List[Dict[str, Any]]:
    """
    Analyzes ALTER TABLE statements for table rewrites and ACCESS EXCLUSIVE locks.
    Calibrated directly from empirical benchmark datasets.
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

    emp_alter = BENCHMARK_MODEL.get_empirical_metrics("ALTER COLUMN TYPE", rows, size_bytes)
    measured_alter_sec = emp_alter["measured_exec_sec"]
    severity_alter = emp_alter["severity"]

    for cmd in commands:
        cmd_type = cmd.get("type")

        # -------------------------------------------------------------
        # Rule 2: ALTER COLUMN TYPE
        # -------------------------------------------------------------
        if cmd_type == "ALTER_COLUMN_TYPE":
            col_name = cmd.get("column", "column_name")
            new_type = cmd.get("new_type", "new_type")
            is_safe = _is_safe_type_change(None, new_type, pg_version)

            if not is_safe:
                safe_sql_snippet = (
                    f"-- Step 1: Add new column (instant metadata change)\n"
                    f"ALTER TABLE {table_name} ADD COLUMN {col_name}_new {new_type};\n\n"
                    f"-- Step 2: Backfill data in bounded batches\n"
                    f"UPDATE {table_name} SET {col_name}_new = {col_name}::{new_type} WHERE {col_name}_new IS NULL LIMIT 5000;\n\n"
                    f"-- Step 3: Deprecate old column and switch reads\n"
                    f"-- ALTER TABLE {table_name} RENAME COLUMN {col_name} TO {col_name}_old;\n"
                    f"-- ALTER TABLE {table_name} RENAME COLUMN {col_name}_new TO {col_name};"
                )

                issues.append({
                    "rule_name": "Potentially Expensive ALTER COLUMN TYPE",
                    "severity": severity_alter,
                    "table": table_name,
                    "line_number": stmt.line_number,
                    "reason": (
                        f"Altering '{col_name}' to '{new_type}' triggers a complete table rewrite under an "
                        f"ACCESS EXCLUSIVE lock, blocking concurrent reads and writes."
                    ),
                    "impact": (
                        f"Table '{table_name}' has ~{rows:,} rows ({size_str}). Measured benchmark duration: "
                        f"{measured_alter_sec:.2f}s under ACCESS EXCLUSIVE lock hold, causing live query queueing."
                    ),
                    "suggestion": "Adopt Expand-Contract migration: add a new column, backfill asynchronously in batches, and switch over.",
                    "doc_url": "https://www.postgresql.org/docs/current/sql-altertable.html",
                    "safe_sql": safe_sql_snippet,
                    "original_sql": stmt.raw_sql,
                    "operation": f"ALTER COLUMN {col_name} TYPE {new_type}",
                    "lock_level": "ACCESS EXCLUSIVE (Full table rewrite)",
                    "estimated_lock_risk": f"Empirical CSV benchmark: {measured_alter_sec:.2f}s rewrite lock",
                })

        # -------------------------------------------------------------
        # Rule 6: ADD COLUMN with default / NOT NULL
        # -------------------------------------------------------------
        elif cmd_type == "ADD_COLUMN":
            col_name = cmd.get("column", "new_col")
            col_type = cmd.get("column_type", "text")
            has_default = cmd.get("has_default", False)
            is_volatile = cmd.get("is_volatile_default", False)
            is_not_null = cmd.get("is_not_null", False)
            default_expr = cmd.get("default_expr", "")

            emp_add = BENCHMARK_MODEL.get_empirical_metrics("ADD COLUMN", rows, size_bytes)
            add_exec_sec = emp_add["measured_exec_sec"]

            # Hazard: Volatile default or (NOT NULL on older PG without fast-default)
            is_hazard = is_volatile or (has_default and is_volatile)
            if pg_version < 110000 and has_default:
                is_hazard = True

            if is_hazard:
                issues.append({
                    "rule_name": "ADD COLUMN with Volatile Default / Table Rewrite",
                    "severity": "HIGH" if rows >= 100_000 else "MEDIUM",
                    "table": table_name,
                    "line_number": stmt.line_number,
                    "reason": (
                        f"ADD COLUMN with volatile default '{default_expr}' rewrites every row on '{table_name}', "
                        f"locking reads and writes under ACCESS EXCLUSIVE."
                    ),
                    "impact": f"Locks entire table for the rewrite duration on ~{rows:,} rows ({size_str}).",
                    "suggestion": "Add column without default first, then populate asynchronously in batches.",
                    "doc_url": "https://www.postgresql.org/docs/current/sql-altertable.html",
                    "safe_sql": (
                        f"-- Step 1: Add column without default\n"
                        f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type};\n"
                        f"-- Step 2: Set default for future rows\n"
                        f"ALTER TABLE {table_name} ALTER COLUMN {col_name} SET DEFAULT {default_expr};\n"
                    ),
                    "original_sql": stmt.raw_sql,
                    "operation": f"ADD COLUMN {col_name}",
                    "lock_level": "ACCESS EXCLUSIVE",
                    "estimated_lock_risk": f"Full table rewrite on ~{rows:,} rows",
                })

    return issues
