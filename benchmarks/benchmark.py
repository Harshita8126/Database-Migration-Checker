"""
Benchmark Harness for Database Migration Safety Checker.
Team Load Balancers - Chitkara University (Hacknauts 2.0)

Measures:
- Background query latency during normal CREATE INDEX vs CREATE INDEX CONCURRENTLY.
- Write query lock wait times and blocked queries.
- p50, p90, p95 latency under real database load.

Outputs:
- benchmark_results.json with measured timeseries and statistics for Plotly visualization.
"""

import time
import json
import argparse
import threading
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import psycopg


def run_workload(
    conninfo: str,
    stop_event: threading.Event,
    results_collector: List[Dict[str, Any]],
    phase_name: str
):
    """Worker thread running continuous read/write queries to measure latency and locking."""
    try:
        conn = psycopg.connect(conninfo, autocommit=True)
        cur = conn.cursor()
        query_idx = 0

        while not stop_event.is_set():
            t0 = time.perf_counter()
            query_type = "read" if (query_idx % 3 != 0) else "write"
            blocked = False

            try:
                if query_type == "read":
                    # Read query
                    cur.execute("SELECT count(*) FROM orders WHERE total_amount > 250 AND status = 'completed';")
                    cur.fetchone()
                else:
                    # Write query - requires ROW EXCLUSIVE lock (blocked by SHARE lock of normal CREATE INDEX)
                    cur.execute(
                        "INSERT INTO orders (customer_id, total_amount, status, notes) "
                        "VALUES (101, 99.99, 'pending', 'Benchmark write probe');"
                    )

                latency_ms = (time.perf_counter() - t0) * 1000.0
                if latency_ms > 200.0 and query_type == "write":
                    blocked = True

                results_collector.append({
                    "phase": phase_name,
                    "timestamp": time.time(),
                    "query_type": query_type,
                    "latency_ms": round(latency_ms, 2),
                    "blocked": blocked,
                })
            except Exception as e:
                # Could fail if locked out or timed out
                latency_ms = (time.perf_counter() - t0) * 1000.0
                results_collector.append({
                    "phase": phase_name,
                    "timestamp": time.time(),
                    "query_type": query_type,
                    "latency_ms": round(latency_ms, 2),
                    "blocked": True,
                    "error": str(e)
                })

            query_idx += 1
            time.sleep(0.05)  # Pace queries at ~20 req/sec per worker

        cur.close()
        conn.close()
    except Exception as exc:
        pass


def execute_migration_test(conninfo: str, workers_count: int = 4) -> Dict[str, Any]:
    """Runs end-to-end benchmark comparing normal vs concurrent index creation."""
    print(">>> Starting Benchmark Harness (Team Load Balancers)...")

    # Connect to verify target test database
    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM orders;")
            row_count = cur.fetchone()[0]
            print(f">>> Connected to test database. Orders table has {row_count:,} rows.")

            # Cleanup any existing benchmark indexes
            cur.execute("DROP INDEX IF EXISTS idx_orders_bench_normal;")
            cur.execute("DROP INDEX IF EXISTS idx_orders_bench_concurrent;")

    all_metrics: List[Dict[str, Any]] = []

    # -------------------------------------------------------------
    # PHASE 1: Normal CREATE INDEX (Unsafe Migration)
    # -------------------------------------------------------------
    print("\n--- PHASE 1: Testing Normal CREATE INDEX (Write-blocking) ---")
    stop_p1 = threading.Event()
    threads_p1 = [
        threading.Thread(target=run_workload, args=(conninfo, stop_p1, all_metrics, "normal_index"))
        for _ in range(workers_count)
    ]
    for t in threads_p1:
        t.start()

    time.sleep(2.0)  # Baseline before migration starts
    p1_start = time.time()

    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            print(">>> Running: CREATE INDEX idx_orders_bench_normal ON orders(total_amount);")
            m_t0 = time.perf_counter()
            cur.execute("CREATE INDEX idx_orders_bench_normal ON orders(total_amount);")
            p1_migration_duration = (time.perf_counter() - m_t0) * 1000.0
            print(f">>> Normal migration finished in {p1_migration_duration:.1f} ms.")

    time.sleep(2.0)  # Cool down after migration
    stop_p1.set()
    for t in threads_p1:
        t.join()

    # Drop index before phase 2
    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP INDEX IF EXISTS idx_orders_bench_normal;")

    time.sleep(2.0)

    # -------------------------------------------------------------
    # PHASE 2: CREATE INDEX CONCURRENTLY (Safe Migration)
    # -------------------------------------------------------------
    print("\n--- PHASE 2: Testing CREATE INDEX CONCURRENTLY (Safe) ---")
    stop_p2 = threading.Event()
    threads_p2 = [
        threading.Thread(target=run_workload, args=(conninfo, stop_p2, all_metrics, "concurrent_index"))
        for _ in range(workers_count)
    ]
    for t in threads_p2:
        t.start()

    time.sleep(2.0)  # Baseline before migration starts
    p2_start = time.time()

    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            print(">>> Running: CREATE INDEX CONCURRENTLY idx_orders_bench_concurrent ON orders(total_amount);")
            m_t0 = time.perf_counter()
            cur.execute("CREATE INDEX CONCURRENTLY idx_orders_bench_concurrent ON orders(total_amount);")
            p2_migration_duration = (time.perf_counter() - m_t0) * 1000.0
            print(f">>> Concurrent migration finished in {p2_migration_duration:.1f} ms.")

    time.sleep(2.0)
    stop_p2.set()
    for t in threads_p2:
        t.join()

    # Cleanup created index
    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP INDEX IF EXISTS idx_orders_bench_concurrent;")

    # -------------------------------------------------------------
    # Calculate Statistical Summary
    # -------------------------------------------------------------
    p1_latencies = [m["latency_ms"] for m in all_metrics if m["phase"] == "normal_index"]
    p1_writes = [m["latency_ms"] for m in all_metrics if m["phase"] == "normal_index" and m["query_type"] == "write"]
    p1_blocked = sum(1 for m in all_metrics if m["phase"] == "normal_index" and m.get("blocked"))

    p2_latencies = [m["latency_ms"] for m in all_metrics if m["phase"] == "concurrent_index"]
    p2_writes = [m["latency_ms"] for m in all_metrics if m["phase"] == "concurrent_index" and m["query_type"] == "write"]
    p2_blocked = sum(1 for m in all_metrics if m["phase"] == "concurrent_index" and m.get("blocked"))

    def compute_stats(arr):
        if not arr:
            return {"p50": 0, "p90": 0, "p95": 0, "max": 0, "avg": 0}
        np_arr = np.array(arr)
        return {
            "p50": round(float(np.percentile(np_arr, 50)), 2),
            "p90": round(float(np.percentile(np_arr, 90)), 2),
            "p95": round(float(np.percentile(np_arr, 95)), 2),
            "max": round(float(np.max(np_arr)), 2),
            "avg": round(float(np.mean(np_arr)), 2),
        }

    summary = {
        "metadata": {
            "test_environment": "Docker PostgreSQL 16 (Test Environment)",
            "table": "orders",
            "row_count": row_count,
            "concurrent_workers": workers_count,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "normal_index": {
            "migration_time_ms": round(p1_migration_duration, 1),
            "blocked_write_queries": p1_blocked,
            "overall_stats": compute_stats(p1_latencies),
            "write_stats": compute_stats(p1_writes),
        },
        "concurrent_index": {
            "migration_time_ms": round(p2_migration_duration, 1),
            "blocked_write_queries": p2_blocked,
            "overall_stats": compute_stats(p2_latencies),
            "write_stats": compute_stats(p2_writes),
        },
        "raw_timeseries": all_metrics[:300],  # Sample for chart rendering
    }

    out_file = Path(__file__).parent / "benchmark_results.json"
    with open(out_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n>>> Benchmark completed! Saved results to {out_file}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PostgreSQL Migration Safety Benchmark")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--dbname", default="migration_test")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--password", default="postgrespassword")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    conn_str = f"host={args.host} port={args.port} dbname={args.dbname} user={args.user} password={args.password}"
    execute_migration_test(conn_str, workers_count=args.workers)
