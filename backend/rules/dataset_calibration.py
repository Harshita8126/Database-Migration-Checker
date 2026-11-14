"""
Empirical Benchmark Metrics Model.
Loads benchmark_dataset CSVs (migration_dataset_v3.csv, performance_dataset_v2.csv)
and provides empirical metrics (execution time, lock hold duration, TPS degradation,
latency spikes) dynamically matched against real table size and row count.
"""

import os
import csv
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks"


class EmpiricalBenchmarkModel:
    """
    In-memory empirical benchmark dataset evaluator.
    Directly loaded from:
      1. migration_dataset_v3.csv (DDL execution times & table byte sizes across 1K, 10K, 100K, 1M rows)
      2. performance_dataset_v2.csv (Concurrent latency, lock delay, TPS changes across 1K, 10K, 100K, 1M rows)
    """

    def __init__(self):
        self.migration_data: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.performance_data: Dict[int, Dict[str, Any]] = {}
        self._load_datasets()

    def _load_datasets(self):
        # 1. Load migration_dataset_v3.csv
        mig_csv = BENCHMARKS_DIR / "migration_dataset_v3.csv"
        if mig_csv.exists():
            try:
                with open(mig_csv, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        op = r.get("operation", "").strip().upper()
                        rows = int(r.get("row_count", 0))
                        exec_sec = float(r.get("execution_time_sec", 0.0))
                        bytes_sz = int(r.get("table_size_bytes", 0))
                        self.migration_data[(op, rows)] = {
                            "execution_time_sec": exec_sec,
                            "table_size_bytes": bytes_sz,
                            "postgres_version": r.get("postgres_version", "18.7"),
                        }
            except Exception as e:
                print(f"[BENCHMARK_MODEL] Warning loading migration_dataset_v3: {e}")

        # 2. Load performance_dataset_v2.csv
        perf_csv = BENCHMARKS_DIR / "performance_dataset_v2.csv"
        if perf_csv.exists():
            try:
                with open(perf_csv, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    # Aggregate repetitions per row_count
                    temp_perf = {}
                    for r in reader:
                        rows = int(r.get("row_count", 0))
                        if rows not in temp_perf:
                            temp_perf[rows] = []
                        temp_perf[rows].append({
                            "concurrent_latency_ms": float(r.get("concurrent_latency_ms", 0.0)),
                            "baseline_latency_ms": float(r.get("baseline_latency_ms", 0.0)),
                            "migration_time_sec": float(r.get("migration_time_sec", 0.0)),
                            "concurrent_tps": float(r.get("concurrent_tps", 0.0)),
                            "baseline_tps": float(r.get("baseline_tps", 0.0)),
                            "concurrent_latency_change_pct": float(r.get("concurrent_latency_change_pct", 0.0)),
                            "concurrent_tps_change_pct": float(r.get("concurrent_tps_change_pct", 0.0)),
                        })

                    # Calculate averages
                    for rows, samples in temp_perf.items():
                        n = len(samples)
                        self.performance_data[rows] = {
                            "avg_concurrent_latency_ms": sum(s["concurrent_latency_ms"] for s in samples) / n,
                            "avg_baseline_latency_ms": sum(s["baseline_latency_ms"] for s in samples) / n,
                            "avg_migration_time_sec": sum(s["migration_time_sec"] for s in samples) / n,
                            "avg_latency_change_pct": sum(s["concurrent_latency_change_pct"] for s in samples) / n,
                            "avg_tps_change_pct": sum(s["concurrent_tps_change_pct"] for s in samples) / n,
                        }
            except Exception as e:
                print(f"[BENCHMARK_MODEL] Warning loading performance_dataset_v2: {e}")

    def get_closest_benchmark_bucket(self, row_count: int, table_bytes: int = 0) -> int:
        """Finds closest calibrated bracket: 1_000, 10_000, 100_000, or 1_000_000."""
        # Check by bytes if rows are 0
        if row_count <= 0 and table_bytes > 0:
            if table_bytes >= 50 * 1024 * 1024:
                return 1_000_000
            elif table_bytes >= 5 * 1024 * 1024:
                return 100_000
            elif table_bytes >= 500 * 1024:
                return 10_000
            else:
                return 1_000

        if row_count >= 500_000:
            return 1_000_000
        elif row_count >= 50_000:
            return 100_000
        elif row_count >= 5_000:
            return 10_000
        else:
            return 1_000

    def get_empirical_metrics(self, operation: str, row_count: int, table_bytes: int = 0) -> Dict[str, Any]:
        """
        Retrieves measured empirical metrics from your real CSV experiments.
        """
        bucket = self.get_closest_benchmark_bucket(row_count, table_bytes)
        op_clean = operation.strip().upper()

        # Direct match in migration dataset
        mig_match = self.migration_data.get((op_clean, bucket))
        if not mig_match:
            # Fallback op mapping
            if "INDEX" in op_clean:
                mig_match = self.migration_data.get(("CREATE INDEX", bucket))
            elif "TYPE" in op_clean:
                mig_match = self.migration_data.get(("ALTER COLUMN TYPE", bucket))
            elif "CONSTRAINT" in op_clean or "NOT NULL" in op_clean:
                mig_match = self.migration_data.get(("ADD CONSTRAINT", bucket))
            elif "ADD COLUMN" in op_clean:
                mig_match = self.migration_data.get(("ADD COLUMN", bucket))
            elif "DROP" in op_clean:
                mig_match = self.migration_data.get(("DROP COLUMN", bucket))

        exec_time = mig_match["execution_time_sec"] if mig_match else 0.05
        dataset_bytes = mig_match["table_size_bytes"] if mig_match else 147456

        perf_match = self.performance_data.get(bucket, {})
        lock_spike_ms = perf_match.get("avg_concurrent_latency_ms", 1.0)
        migration_dur_sec = perf_match.get("avg_migration_time_sec", exec_time)

        # Risk severity thresholds derived strictly from CSV data:
        # 1M rows: CREATE INDEX takes 12.4s (or 42-79s during workload), ALTER COLUMN TYPE takes 5.12s
        # 100K rows: CREATE INDEX takes 0.53s, ALTER COLUMN TYPE takes 0.27s
        # 10K rows: takes 0.02s - 0.06s
        # 1K rows: takes < 0.008s
        if bucket >= 100_000:
            severity = "HIGH"
        elif bucket >= 10_000:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return {
            "bucket_rows": bucket,
            "measured_exec_sec": exec_time,
            "measured_table_bytes": dataset_bytes,
            "measured_lock_spike_ms": lock_spike_ms,
            "migration_time_sec": migration_dur_sec,
            "severity": severity,
        }


# Singleton instance
BENCHMARK_MODEL = EmpiricalBenchmarkModel()
