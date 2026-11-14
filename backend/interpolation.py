"""
Size-based Log-Log Interpolation Module for PostgreSQL Migration Safety Checker.

Estimates indicative migration execution duration (in milliseconds) for intermediate
table sizes by log-log interpolation between nearest benchmarked measurements
for the SAME operation type.

IMPORTANT DESIGN RULES:
1. Reference/Output only: Execution time is machine-dependent and indicative.
   It must NEVER be used to decide risk levels.
2. Operation isolation: Interpolation is performed strictly per operation type.
3. Log-log interpolation: Table size vs time follows an empirical power law.
   x = log(row_count), y = log(time_ms), np.interp on logs, then np.exp the result.
4. No extrapolation: If user_rows is strictly below min or strictly above max
   benchmarked rows for that operation, returns status 'out_of_range' with None times.
5. Exact match: If user_rows matches a benchmark size, returns measured value ('exact').
6. No data / Insufficient data: If operation not found ('no_data') or has < 2 points
   ('insufficient_data').
"""

import math
from typing import Dict, Any, Optional, Union
import numpy as np
import pandas as pd

# Heuristic range band fraction: ±25% around estimate when repeated min/max is absent.
# Documented clearly as a heuristic display range, NOT a formal statistical interval.
BAND_FRACTION = 0.25


def _clean_and_aggregate_operation_data(
    df: pd.DataFrame,
    operation: str,
    op_col: str = "operation",
    row_col: str = "row_count",
    time_col: str = "execution_time_sec",
    time_is_seconds: bool = True
) -> pd.DataFrame:
    """
    Filters, sanitizes, and aggregates benchmarks for a specific operation.
    Groups by row_count, calculates median time, converts to milliseconds,
    and sorts ascending by row_count.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Case-insensitive & stripped matching on operation
    target_op = str(operation).strip().upper()
    sub_df = df.copy()

    # Drop non-existent columns
    if op_col not in sub_df.columns or row_col not in sub_df.columns or time_col not in sub_df.columns:
        return pd.DataFrame()

    sub_df["_clean_op"] = sub_df[op_col].astype(str).str.strip().str.upper()
    sub_df = sub_df[sub_df["_clean_op"] == target_op]

    if sub_df.empty:
        return pd.DataFrame()

    # Coerce numeric values and drop NaNs
    sub_df["_rows"] = pd.to_numeric(sub_df[row_col], errors="coerce")
    sub_df["_time"] = pd.to_numeric(sub_df[time_col], errors="coerce")

    # Drop NaN, zero, or negative (log will fail)
    sub_df = sub_df.dropna(subset=["_rows", "_time"])
    sub_df = sub_df[(sub_df["_rows"] > 0) & (sub_df["_time"] > 0)]

    if sub_df.empty:
        return pd.DataFrame()

    # Convert to milliseconds if needed
    mult = 1000.0 if time_is_seconds else 1.0
    sub_df["_time_ms"] = sub_df["_time"] * mult

    # Check for repetition min/max if present in raw data
    has_min_max = "min_time" in sub_df.columns and "max_time" in sub_df.columns

    if has_min_max:
        agg_dict = {
            "_time_ms": "median",
            "min_time_ms": ("min_time", lambda s: np.nanmedian(s) * mult),
            "max_time_ms": ("max_time", lambda s: np.nanmedian(s) * mult),
        }
    else:
        # Check if multiple repetitions exist per row_count to compute empirical min/max
        agg_dict = {
            "_time_ms": "median",
            "raw_min_ms": ("_time_ms", "min"),
            "raw_max_ms": ("_time_ms", "max"),
            "sample_count": ("_time_ms", "count")
        }

    grouped = sub_df.groupby("_rows").agg(
        median_ms=("_time_ms", "median"),
        min_ms=("_time_ms", "min"),
        max_ms=("_time_ms", "max"),
        count=("_time_ms", "count")
    ).reset_index()

    grouped = grouped.sort_values(by="_rows").reset_index(drop=True)
    return grouped


def estimate_time(
    df: pd.DataFrame,
    operation: str,
    user_rows: int,
    op_col: str = "operation",
    row_col: str = "row_count",
    time_col: str = "execution_time_sec",
    time_is_seconds: bool = True
) -> Dict[str, Any]:
    """
    Estimates indicative execution duration (in ms) using log-log interpolation.

    Returns:
    {
      "status": "exact" | "interpolated" | "out_of_range" | "no_data" | "insufficient_data",
      "estimate_ms": float | None,
      "low_ms": float | None,
      "high_ms": float | None,
      "lower_neighbor": {"rows": int, "time_ms": float} | None,
      "upper_neighbor": {"rows": int, "time_ms": float} | None,
      "note": "Indicative, interpolated from benchmarks on our test machine. Actual time depends on hardware and load."
    }
    """
    note_msg = "Indicative, interpolated from benchmarks on our test machine. Actual time depends on hardware and load."

    empty_result = {
        "status": "no_data",
        "estimate_ms": None,
        "low_ms": None,
        "high_ms": None,
        "lower_neighbor": None,
        "upper_neighbor": None,
        "note": note_msg,
    }

    if df is None or df.empty or not operation:
        return empty_result

    # Handle invalid user_rows input
    if user_rows is None or not isinstance(user_rows, (int, float)) or user_rows <= 0 or math.isnan(user_rows):
        res = dict(empty_result)
        res["status"] = "out_of_range"
        return res

    user_rows_val = int(user_rows)

    clean_df = _clean_and_aggregate_operation_data(
        df,
        operation=operation,
        op_col=op_col,
        row_col=row_col,
        time_col=time_col,
        time_is_seconds=time_is_seconds,
    )

    if clean_df.empty:
        return empty_result

    distinct_points = len(clean_df)
    if distinct_points < 2:
        res = dict(empty_result)
        res["status"] = "insufficient_data"
        if distinct_points == 1:
            row_pt = int(clean_df.iloc[0]["_rows"])
            time_pt = float(clean_df.iloc[0]["median_ms"])
            if user_rows_val == row_pt:
                res["status"] = "exact"
                res["estimate_ms"] = time_pt
                res["low_ms"] = time_pt * (1.0 - BAND_FRACTION)
                res["high_ms"] = time_pt * (1.0 + BAND_FRACTION)
                res["lower_neighbor"] = {"rows": row_pt, "time_ms": time_pt}
                res["upper_neighbor"] = {"rows": row_pt, "time_ms": time_pt}
        return res

    rows_arr = clean_df["_rows"].values.astype(float)
    times_arr = clean_df["median_ms"].values.astype(float)
    min_rows = rows_arr[0]
    max_rows = rows_arr[-1]

    # Rule 4: No extrapolation
    if user_rows_val < min_rows or user_rows_val > max_rows:
        res = dict(empty_result)
        res["status"] = "out_of_range"
        return res

    # Rule 5: Exact match
    exact_idx = np.where(rows_arr == user_rows_val)[0]
    if len(exact_idx) > 0:
        idx = exact_idx[0]
        t_exact = float(times_arr[idx])
        # If repetitions had variation, use empirical min/max, otherwise use BAND_FRACTION heuristic
        c_min = float(clean_df.iloc[idx]["min_ms"])
        c_max = float(clean_df.iloc[idx]["max_ms"])
        low_val = c_min if c_min < t_exact else t_exact * (1.0 - BAND_FRACTION)
        high_val = c_max if c_max > t_exact else t_exact * (1.0 + BAND_FRACTION)

        pt_dict = {"rows": int(rows_arr[idx]), "time_ms": round(t_exact, 4)}
        return {
            "status": "exact",
            "estimate_ms": round(t_exact, 4),
            "low_ms": round(low_val, 4),
            "high_ms": round(high_val, 4),
            "lower_neighbor": pt_dict,
            "upper_neighbor": pt_dict,
            "note": note_msg,
        }

    # Find lower and upper neighbors
    upper_idx = np.searchsorted(rows_arr, user_rows_val)
    lower_idx = upper_idx - 1

    r_low, t_low = rows_arr[lower_idx], times_arr[lower_idx]
    r_high, t_high = rows_arr[upper_idx], times_arr[upper_idx]

    # Rule 3: Log-log interpolation
    log_x = np.log([r_low, r_high])
    log_y = np.log([t_low, t_high])
    target_log_x = np.log(user_rows_val)

    interpolated_log_y = float(np.interp(target_log_x, log_x, log_y))
    estimate_ms = float(np.exp(interpolated_log_y))

    # Range band (low_ms / high_ms)
    # Check if we can interpolate min_ms and max_ms
    min_arr = clean_df["min_ms"].values.astype(float)
    max_arr = clean_df["max_ms"].values.astype(float)

    has_measured_spread = (min_arr[lower_idx] < t_low or max_arr[lower_idx] > t_low or
                          min_arr[upper_idx] < t_high or max_arr[upper_idx] > t_high)

    if has_measured_spread and min_arr[lower_idx] > 0 and min_arr[upper_idx] > 0 and max_arr[lower_idx] > 0 and max_arr[upper_idx] > 0:
        log_y_low = np.log([min_arr[lower_idx], min_arr[upper_idx]])
        log_y_high = np.log([max_arr[lower_idx], max_arr[upper_idx]])
        low_ms = float(np.exp(np.interp(target_log_x, log_x, log_y_low)))
        high_ms = float(np.exp(np.interp(target_log_x, log_x, log_y_high)))
    else:
        # Heuristic band fraction as specified in requirements
        low_ms = estimate_ms * (1.0 - BAND_FRACTION)
        high_ms = estimate_ms * (1.0 + BAND_FRACTION)

    return {
        "status": "interpolated",
        "estimate_ms": round(estimate_ms, 4),
        "low_ms": round(low_ms, 4),
        "high_ms": round(high_ms, 4),
        "lower_neighbor": {"rows": int(r_low), "time_ms": round(float(t_low), 4)},
        "upper_neighbor": {"rows": int(r_high), "time_ms": round(float(t_high), 4)},
        "note": note_msg,
    }


def scaling_factor(
    df: pd.DataFrame,
    operation: str,
    op_col: str = "operation",
    row_col: str = "row_count",
    time_col: str = "execution_time_sec",
    time_is_seconds: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Computes relative scaling factor:
    time at largest benchmarked size / time at smallest benchmarked size.
    Since relative scaling is less machine-dependent than raw timings.
    """
    clean_df = _clean_and_aggregate_operation_data(
        df,
        operation=operation,
        op_col=op_col,
        row_col=row_col,
        time_col=time_col,
        time_is_seconds=time_is_seconds,
    )

    if clean_df.empty or len(clean_df) < 2:
        return None

    smallest_row = int(clean_df.iloc[0]["_rows"])
    largest_row = int(clean_df.iloc[-1]["_rows"])
    time_smallest = float(clean_df.iloc[0]["median_ms"])
    time_largest = float(clean_df.iloc[-1]["median_ms"])

    if time_smallest <= 0:
        return None

    factor = time_largest / time_smallest
    return {
        "factor": round(factor, 2),
        "smallest_rows": smallest_row,
        "largest_rows": largest_row,
        "time_smallest_ms": round(time_smallest, 4),
        "time_largest_ms": round(time_largest, 4),
        "text": f"{largest_row:,} rows takes ~{factor:.1f}x longer than {smallest_row:,} rows",
    }
