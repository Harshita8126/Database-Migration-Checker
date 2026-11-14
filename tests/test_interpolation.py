"""
Unit tests for the size-based log-log interpolation module.

Tests cover:
- Exact matches at benchmarked points
- In-between values (verifying estimate strictly lies between neighbor times)
- Out-of-range bounds (below min and above max)
- Unknown operations ('no_data')
- Single-size operations ('insufficient_data')
- Aggregating repeated measurements using MEDIAN
- Dropping zero, negative, and NaN rows
- Monotonicity checks
- Scaling factor helper
"""

import math
import numpy as np
import pandas as pd
import pytest

from backend.interpolation import estimate_time, scaling_factor, BAND_FRACTION


@pytest.fixture
def sample_benchmark_df():
    """
    Standard clean benchmark dataset with multiple table sizes and an operation.
    """
    return pd.DataFrame({
        "operation": ["CREATE INDEX", "CREATE INDEX", "CREATE INDEX", "CREATE INDEX"],
        "row_count": [1000, 10000, 100000, 1000000],
        "execution_time_sec": [0.005, 0.05, 0.50, 12.0],
    })


@pytest.fixture
def repeated_measurements_df():
    """
    Benchmark dataset with repeated runs per row_count (testing median aggregation).
    """
    return pd.DataFrame({
        "operation": [
            "CREATE INDEX", "CREATE INDEX", "CREATE INDEX",
            "CREATE INDEX", "CREATE INDEX", "CREATE INDEX",
        ],
        "row_count": [
            1000, 1000, 1000,
            10000, 10000, 10000,
        ],
        # Medians will be 0.005 and 0.050 respectively
        "execution_time_sec": [
            0.003, 0.005, 0.010,
            0.040, 0.050, 0.090,
        ],
    })


def test_exact_match(sample_benchmark_df):
    """If user_rows exactly matches a benchmarked size, return that measured value."""
    res = estimate_time(sample_benchmark_df, "CREATE INDEX", 10000)
    assert res["status"] == "exact"
    assert res["estimate_ms"] == pytest.approx(50.0, rel=1e-3)
    assert res["lower_neighbor"]["rows"] == 10000
    assert res["upper_neighbor"]["rows"] == 10000
    assert res["low_ms"] <= res["estimate_ms"] <= res["high_ms"]


def test_in_between_interpolation(sample_benchmark_df):
    """
    For user_rows between 10K and 100K (e.g. 50K), estimate must be
    strictly between lower and upper neighbor times.
    """
    res = estimate_time(sample_benchmark_df, "CREATE INDEX", 50000)
    assert res["status"] == "interpolated"
    assert res["estimate_ms"] is not None

    lower_time = res["lower_neighbor"]["time_ms"]
    upper_time = res["upper_neighbor"]["time_ms"]
    assert res["lower_neighbor"]["rows"] == 10000
    assert res["upper_neighbor"]["rows"] == 100000
    assert lower_time < res["estimate_ms"] < upper_time

    # Range band must flank the estimate
    assert res["low_ms"] < res["estimate_ms"] < res["high_ms"]


def test_below_min_out_of_range(sample_benchmark_df):
    """Below min size returns out_of_range with None times."""
    res = estimate_time(sample_benchmark_df, "CREATE INDEX", 500)
    assert res["status"] == "out_of_range"
    assert res["estimate_ms"] is None
    assert res["low_ms"] is None
    assert res["high_ms"] is None


def test_above_max_out_of_range(sample_benchmark_df):
    """Above max size returns out_of_range with None times."""
    res = estimate_time(sample_benchmark_df, "CREATE INDEX", 5000000)
    assert res["status"] == "out_of_range"
    assert res["estimate_ms"] is None


def test_unknown_operation(sample_benchmark_df):
    """Operations with no rows in the CSV return status 'no_data'."""
    res = estimate_time(sample_benchmark_df, "UNKNOWN_OPERATION_XYZ", 50000)
    assert res["status"] == "no_data"
    assert res["estimate_ms"] is None


def test_single_size_operation():
    """An operation with only 1 benchmarked size cannot be interpolated."""
    df = pd.DataFrame({
        "operation": ["VACUUM"],
        "row_count": [10000],
        "execution_time_sec": [0.2],
    })
    # Intermediate check
    res = estimate_time(df, "VACUUM", 5000)
    assert res["status"] == "insufficient_data"


def test_repeated_measurements_median_aggregation(repeated_measurements_df):
    """Repeated measurements are aggregated by MEDIAN, ignoring outliers."""
    res_1k = estimate_time(repeated_measurements_df, "CREATE INDEX", 1000)
    assert res_1k["status"] == "exact"
    # median of [3ms, 5ms, 10ms] = 5ms
    assert res_1k["estimate_ms"] == pytest.approx(5.0, rel=1e-3)

    res_10k = estimate_time(repeated_measurements_df, "CREATE INDEX", 10000)
    assert res_10k["status"] == "exact"
    # median of [40ms, 50ms, 90ms] = 50ms
    assert res_10k["estimate_ms"] == pytest.approx(50.0, rel=1e-3)


def test_zero_negative_nan_filtering():
    """Rows with NaN, zero, or negative row_count/time are safely dropped."""
    df = pd.DataFrame({
        "operation": ["ADD COLUMN", "ADD COLUMN", "ADD COLUMN", "ADD COLUMN", "ADD COLUMN"],
        "row_count": [0, -500, np.nan, 1000, 10000],
        "execution_time_sec": [0.01, 0.02, 0.03, -0.05, 0.005],  # 1000 has negative time -> dropped
    })
    # Only 10000 has valid row & time -> single point left -> insufficient_data for interpolation
    res = estimate_time(df, "ADD COLUMN", 5000)
    assert res["status"] == "insufficient_data"


def test_monotonic_sanity(sample_benchmark_df):
    """Monotonic check: larger table size produces strictly larger estimated duration."""
    est_20k = estimate_time(sample_benchmark_df, "CREATE INDEX", 20000)["estimate_ms"]
    est_50k = estimate_time(sample_benchmark_df, "CREATE INDEX", 50000)["estimate_ms"]
    est_80k = estimate_time(sample_benchmark_df, "CREATE INDEX", 80000)["estimate_ms"]

    assert est_20k < est_50k < est_80k


def test_scaling_factor(sample_benchmark_df):
    """Helper computes relative scaling factor between largest and smallest points."""
    scale = scaling_factor(sample_benchmark_df, "CREATE INDEX")
    assert scale is not None
    assert scale["smallest_rows"] == 1000
    assert scale["largest_rows"] == 1000000
    # 12.0s / 0.005s = 2400x
    assert scale["factor"] == pytest.approx(2400.0, rel=1e-2)
