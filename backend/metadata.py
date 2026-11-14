"""
PostgreSQL Metadata Inspector.


Safely queries PostgreSQL catalogs:
- pg_stat_user_tables (estimated live & dead row counts)
- pg_class & pg_total_relation_size() (physical table & index disk sizes)
- pg_indexes & pg_constraint (existing indices and constraints)
- pg_stat_activity & pg_locks (long-running transactions / lock-queue warning)
- Server version and capabilities

Also provides manual fallback & realistic mock metadata for hackathon demonstrations.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import psycopg


@dataclass
class TableMetadata:
    table_name: str
    schema_name: str = "public"
    estimated_rows: int = 0
    dead_rows: int = 0
    total_size_bytes: int = 0
    total_size_pretty: str = "0 kB"
    indexes: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    long_running_queries: List[Dict[str, Any]] = field(default_factory=list)
    is_mock: bool = False
    source: str = "live_db"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _bytes_to_pretty(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} kB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def fetch_table_metadata(conn: psycopg.Connection, table_name: str, schema_name: str = "public") -> TableMetadata:
    """
    Queries catalog for a specific table's live row estimates, byte size,
    existing indexes, constraints, and active lock queues.
    Handles missing tables and permissions safely.
    """
    meta = TableMetadata(table_name=table_name, schema_name=schema_name)

    try:
        with conn.cursor() as cur:
            # 1. Live row estimates from pg_stat_user_tables
            cur.execute(
                """
                SELECT n_live_tup, n_dead_tup
                FROM pg_stat_user_tables
                WHERE relname = %s AND schemaname = %s;
                """,
                (table_name, schema_name)
            )
            stat_row = cur.fetchone()
            if stat_row:
                meta.estimated_rows = int(stat_row[0] or 0)
                meta.dead_rows = int(stat_row[1] or 0)
            else:
                # Fallback to pg_class reltuples
                cur.execute(
                    """
                    SELECT c.reltuples
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = %s AND n.nspname = %s;
                    """,
                    (table_name, schema_name)
                )
                class_row = cur.fetchone()
                if class_row and class_row[0] is not None:
                    meta.estimated_rows = max(0, int(class_row[0]))

            # 2. Total relation size (table + indexes + toast)
            try:
                cur.execute(
                    """
                    SELECT pg_total_relation_size(format('%I.%I', %s, %s)),
                           pg_size_pretty(pg_total_relation_size(format('%I.%I', %s, %s)));
                    """,
                    (schema_name, table_name, schema_name, table_name)
                )
                size_row = cur.fetchone()
                if size_row:
                    meta.total_size_bytes = int(size_row[0] or 0)
                    meta.total_size_pretty = str(size_row[1] or "0 kB")
            except Exception:
                # In case table doesn't exist yet or permissions are restricted
                pass

            # 3. Existing indexes
            try:
                cur.execute(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = %s AND schemaname = %s;
                    """,
                    (table_name, schema_name)
                )
                for i_row in cur.fetchall():
                    meta.indexes.append({
                        "name": i_row[0],
                        "definition": i_row[1]
                    })
            except Exception:
                pass

            # 4. Existing constraints
            try:
                cur.execute(
                    """
                    SELECT c.conname, c.contype, pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    JOIN pg_namespace n ON t.relnamespace = n.oid
                    WHERE t.relname = %s AND n.nspname = %s;
                    """,
                    (table_name, schema_name)
                )
                contype_map = {'p': 'PRIMARY KEY', 'f': 'FOREIGN KEY', 'c': 'CHECK', 'u': 'UNIQUE'}
                for c_row in cur.fetchall():
                    meta.constraints.append({
                        "name": c_row[0],
                        "type": contype_map.get(c_row[1], c_row[1]),
                        "definition": c_row[2]
                    })
            except Exception:
                pass

            # 5. Lock-queue check (active queries > 5s that could block or be blocked)
            try:
                cur.execute(
                    """
                    SELECT pid, extract(epoch from (now() - xact_start))::int as duration_sec, state, query
                    FROM pg_stat_activity
                    WHERE state != 'idle' 
                      AND pid != pg_backend_pid()
                      AND xact_start < now() - interval '5 seconds'
                    ORDER BY xact_start ASC
                    LIMIT 5;
                    """
                )
                for q_row in cur.fetchall():
                    meta.long_running_queries.append({
                        "pid": q_row[0],
                        "duration_sec": q_row[1],
                        "state": q_row[2],
                        "query_snippet": (q_row[3] or "")[:80]
                    })
            except Exception:
                pass

    except Exception:
        # Graceful return with default/empty values if permissions are limited
        pass

    return meta


def create_manual_metadata(
    table_name: str,
    estimated_rows: int = 1000000,
    size_mb: float = 250.0,
    schema_name: str = "public"
) -> TableMetadata:
    """Creates a manual TableMetadata object for offline or user-specified analysis."""
    bytes_val = int(size_mb * 1024 * 1024)
    return TableMetadata(
        table_name=table_name,
        schema_name=schema_name,
        estimated_rows=estimated_rows,
        dead_rows=int(estimated_rows * 0.05),
        total_size_bytes=bytes_val,
        total_size_pretty=_bytes_to_pretty(bytes_val),
        is_mock=True,
        source="manual_input"
    )


def get_demo_production_metadata() -> Dict[str, TableMetadata]:
    """
    Returns realistic production database metadata for demo and hackathon presentation.
    Simulates a high-traffic e-commerce and fintech system.
    """
    return {
        "orders": TableMetadata(
            table_name="orders",
            schema_name="public",
            estimated_rows=12_450_000,
            dead_rows=310_000,
            total_size_bytes=4_450_000_000,
            total_size_pretty="4.14 GB",
            indexes=[
                {"name": "orders_pkey", "definition": "CREATE UNIQUE INDEX orders_pkey ON orders USING btree (id)"},
                {"name": "idx_orders_customer_id", "definition": "CREATE INDEX idx_orders_customer_id ON orders USING btree (customer_id)"},
                {"name": "idx_orders_created_at", "definition": "CREATE INDEX idx_orders_created_at ON orders USING btree (created_at)"},
            ],
            constraints=[
                {"name": "orders_pkey", "type": "PRIMARY KEY", "definition": "PRIMARY KEY (id)"},
                {"name": "fk_customer", "type": "FOREIGN KEY", "definition": "FOREIGN KEY (customer_id) REFERENCES customers(id)"},
            ],
            long_running_queries=[
                {
                    "pid": 4821,
                    "duration_sec": 42,
                    "state": "active",
                    "query_snippet": "SELECT customer_id, sum(total_amount) FROM orders WHERE created_at > ..."
                }
            ],
            is_mock=True,
            source="demo_production_db"
        ),
        "users": TableMetadata(
            table_name="users",
            schema_name="public",
            estimated_rows=3_200_000,
            dead_rows=45_000,
            total_size_bytes=890_000_000,
            total_size_pretty="848.7 MB",
            indexes=[
                {"name": "users_pkey", "definition": "CREATE UNIQUE INDEX users_pkey ON users USING btree (id)"},
                {"name": "users_email_key", "definition": "CREATE UNIQUE INDEX users_email_key ON users USING btree (email)"},
            ],
            constraints=[
                {"name": "users_pkey", "type": "PRIMARY KEY", "definition": "PRIMARY KEY (id)"},
                {"name": "users_email_key", "type": "UNIQUE", "definition": "UNIQUE (email)"},
            ],
            is_mock=True,
            source="demo_production_db"
        ),
        "payments": TableMetadata(
            table_name="payments",
            schema_name="public",
            estimated_rows=18_700_000,
            dead_rows=520_000,
            total_size_bytes=7_600_000_000,
            total_size_pretty="7.08 GB",
            indexes=[
                {"name": "payments_pkey", "definition": "CREATE UNIQUE INDEX payments_pkey ON payments USING btree (id)"},
                {"name": "idx_payments_order_id", "definition": "CREATE INDEX idx_payments_order_id ON payments USING btree (order_id)"},
            ],
            constraints=[
                {"name": "payments_pkey", "type": "PRIMARY KEY", "definition": "PRIMARY KEY (id)"},
            ],
            is_mock=True,
            source="demo_production_db"
        ),
        "customers": TableMetadata(
            table_name="customers",
            schema_name="public",
            estimated_rows=2_800_000,
            dead_rows=22_000,
            total_size_bytes=620_000_000,
            total_size_pretty="591.3 MB",
            indexes=[
                {"name": "customers_pkey", "definition": "CREATE UNIQUE INDEX customers_pkey ON customers USING btree (id)"},
            ],
            constraints=[
                {"name": "customers_pkey", "type": "PRIMARY KEY", "definition": "PRIMARY KEY (id)"},
            ],
            is_mock=True,
            source="demo_production_db"
        ),
    }
