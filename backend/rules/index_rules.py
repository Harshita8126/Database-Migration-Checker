"""
Migration Safety Rule: Index Creation Rules.
Calibrated directly against real benchmark datasets:
- benchmarks/migration_dataset_v3.csv (Execution & lock duration on 1K, 10K, 100K, 1M rows)
- benchmarks/performance_dataset_v2.csv (Latency spikes & TPS degradation under concurrent workload)
"""

from typing import List, Dict, Any, Optional
from backend.parser import ParsedStatement
from backend.metadata import TableMetadata
from backend.rules.dataset_calibration import BENCHMARK_MODEL


def check_index_rules(
    stmt: ParsedStatement,
    metadata_map: Dict[str, TableMetadata],
    pg_version: int = 150000
) -> List[Dict[str, Any]]:
    """
    Analyzes CREATE INDEX statements for write-blocking hazards.
    Derives risk severity and impact metrics directly from empirical CSV benchmarks.
    """
    issues = []
    if stmt.statement_type != "CREATE INDEX":
        return issues

    details = stmt.details
    table_name = stmt.table_name or "unknown_table"
    is_concurrent = details.get("concurrent", False)
    index_name = details.get("index_name") or f"idx_{table_name}_col"
    columns = details.get("columns", [])
    cols_str = ", ".join(columns) if columns else "..."
    unique_kw = "UNIQUE " if details.get("unique", False) else ""

    meta = metadata_map.get(table_name)
    rows = meta.estimated_rows if meta else 0
    size_bytes = meta.total_size_bytes if meta else 0
    size_str = meta.total_size_pretty if meta else "unknown size"

    # Empirical dataset metrics matching table scale
    emp = BENCHMARK_MODEL.get_empirical_metrics("CREATE INDEX", rows, size_bytes)
    measured_sec = emp["measured_exec_sec"]
    lock_spike = emp["measured_lock_spike_ms"]
    severity = emp["severity"]

    # Rule 1: Non-concurrent index creation
    if not is_concurrent:
        if severity == "HIGH":
            impact_desc = (
                f"Blocks all INSERT/UPDATE/DELETE traffic on '{table_name}' (~{rows:,} rows, {size_str}). "
                f"Empirical benchmarks (migration_dataset_v3.csv & performance_dataset_v2.csv) record an unshielded "
                f"lock hold time of {measured_sec:.2f}s with write latencies spiking to {lock_spike:.1f}ms under concurrent traffic."
            )
        elif severity == "MEDIUM":
            impact_desc = (
                f"Acquires SHARE lock on '{table_name}' (~{rows:,} rows, {size_str}). "
                f"Empirical benchmark records {measured_sec:.3f}s lock hold, causing queued write transactions."
            )
        else:
            impact_desc = (
                f"Acquires SHARE lock on table '{table_name}' (~{rows:,} rows). Measured duration: {measured_sec:.4f}s. "
                f"While fast on small tables, non-concurrent index creation violates production zero-downtime guidelines."
            )

        raw_upper = stmt.raw_sql.strip()
        if "CREATE UNIQUE INDEX" in raw_upper.upper():
            safe_sql = raw_upper.replace("CREATE UNIQUE INDEX", "CREATE UNIQUE INDEX CONCURRENTLY", 1)
        elif "CREATE INDEX" in raw_upper.upper():
            safe_sql = raw_upper.replace("CREATE INDEX", "CREATE INDEX CONCURRENTLY", 1)
        else:
            safe_sql = f"CREATE {unique_kw}INDEX CONCURRENTLY {index_name} ON {table_name}({cols_str});"

        issues.append({
            "rule_name": "Non-Concurrent Index Creation",
            "severity": severity,
            "table": table_name,
            "line_number": stmt.line_number,
            "reason": (
                f"CREATE INDEX acquires a SHARE lock on '{table_name}', blocking all INSERT, UPDATE, and DELETE queries "
                f"until complete."
            ),
            "impact": impact_desc,
            "suggestion": "Build the index using the CONCURRENTLY modifier to permit uninterrupted reads and writes.",
            "doc_url": "https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY",
            "safe_sql": safe_sql,
            "original_sql": stmt.raw_sql,
            "operation": "CREATE INDEX",
            "lock_level": "SHARE (Blocks writes)",
            "estimated_lock_risk": f"Empirical CSV benchmark: {measured_sec:.2f}s lock hold",
        })

    return issues
