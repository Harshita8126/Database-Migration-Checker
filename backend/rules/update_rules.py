"""
Migration Safety Rule: UPDATE and DROP Rules.


Detects:
- Large or unbounded UPDATE statements (long transactions, WAL bloat, lock contention).
- Dangerous DROP TABLE or DROP COLUMN operations.
"""

from typing import List, Dict, Any, Optional
from backend.parser import ParsedStatement
from backend.metadata import TableMetadata


def check_update_rules(
    stmt: ParsedStatement,
    metadata_map: Dict[str, TableMetadata],
    pg_version: int = 150000
) -> List[Dict[str, Any]]:
    """
    Analyzes UPDATE and DROP statements for transaction bloat and data loss hazards.
    """
    issues = []
    table_name = stmt.table_name or "unknown_table"
    meta = metadata_map.get(table_name)
    rows = meta.estimated_rows if meta else 0
    size_str = meta.total_size_pretty if meta else "unknown size"

    # -------------------------------------------------------------
    # Rule 5: Large / Unbounded UPDATE
    # -------------------------------------------------------------
    if stmt.statement_type == "UPDATE":
        details = stmt.details
        has_where = details.get("has_where", False)
        target_cols = ", ".join(details.get("target_columns", ["column"]))

        if not has_where:
            if rows >= 100_000 or (meta and meta.total_size_bytes >= 9 * 1024 * 1024):
                severity = "HIGH"
            elif rows >= 10_000 or (meta and meta.total_size_bytes >= 1024 * 1024):
                severity = "MEDIUM"
            else:
                severity = "LOW"
            
            safe_sql = (
                f"-- Safe batched backfill pattern\n"
                f"WITH batch AS (\n"
                f"    SELECT ctid FROM {table_name}\n"
                f"    LIMIT 5000\n"
                f"    FOR UPDATE SKIP LOCKED\n"
                f")\n"
                f"UPDATE {table_name} t\n"
                f"SET {target_cols} = ...\n"
                f"FROM batch\n"
                f"WHERE t.ctid = batch.ctid;"
            )

            issues.append({
                "rule_name": "Unbounded Table UPDATE",
                "severity": severity,
                "table": table_name,
                "line_number": stmt.line_number,
                "reason": (
                    f"UPDATE on '{table_name}' lacks a WHERE clause, modifying all rows in a single monolithic transaction."
                ),
                "impact": (
                    f"Table '{table_name}' has ~{rows:,} rows ({size_str}). Monolithic updates cause transaction bloat, "
                    f"replication lag, and extensive row-lock contention."
                ),
                "suggestion": "Execute the backfill in bounded batches (e.g. 2,000–5,000 rows) with pauses between iterations.",
                "doc_url": "https://www.postgresql.org/docs/current/sql-update.html",
                "safe_sql": safe_sql,
                "original_sql": stmt.raw_sql,
                "operation": f"UPDATE {table_name}",
                "lock_level": "ROW EXCLUSIVE (Entire table)",
                "estimated_lock_risk": f"Row locks across ~{rows:,} rows" if rows > 0 else "Row locks across entire table",
            })

    # -------------------------------------------------------------
    # Rule 8: DROP TABLE or DROP COLUMN
    # -------------------------------------------------------------
    elif stmt.statement_type.startswith("DROP") or (
        stmt.statement_type == "ALTER TABLE" and any(c.get("type") == "DROP_COLUMN" for c in stmt.details.get("commands", []))
    ):
        target_name = table_name
        is_col_drop = stmt.statement_type == "ALTER TABLE"
        col_name = ""
        if is_col_drop:
            for c in stmt.details.get("commands", []):
                if c.get("type") == "DROP_COLUMN":
                    col_name = c.get("column", "")

        severity = "HIGH"
        safe_sql = (
            f"-- Step 1: Deprecate {col_name or target_name} in application code and deploy.\n"
            f"-- Step 2: Drop during scheduled maintenance window after verifying zero traffic:\n"
            f"{stmt.raw_sql}"
        )

        issues.append({
            "rule_name": f"Destructive {'DROP COLUMN' if is_col_drop else 'DROP TABLE'}",
            "severity": severity,
            "table": table_name,
            "line_number": stmt.line_number,
            "reason": (
                f"Dropping {'column ' + col_name if is_col_drop else 'table ' + target_name} permanently deletes data "
                f"under an ACCESS EXCLUSIVE lock, terminating concurrent queries."
            ),
            "impact": "Irreversible schema deletion and immediate failure if any running service references it.",
            "suggestion": "Remove application references first, then drop the object in a separate maintenance release.",
            "doc_url": "https://www.postgresql.org/docs/current/ddl-alter.html",
            "safe_sql": safe_sql,
            "original_sql": stmt.raw_sql,
            "operation": f"DROP {'COLUMN ' + col_name if is_col_drop else 'TABLE ' + target_name}",
            "lock_level": "ACCESS EXCLUSIVE",
            "estimated_lock_risk": "Immediate destructive lock",
        })

    return issues
