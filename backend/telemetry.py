"""
RaceBox — telemetry.py
Driver telemetry comparison, sector time breakdowns, speed trace
analysis, and GPS coordinate generation for heatmaps.
"""
from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd

from backend.data_loader import load_session, get_driver_telemetry


def compare_drivers_telemetry(year: int, gp: str | int,
                               driver_a: str, driver_b: str,
                               lap_number: Optional[int] = None) -> dict:
    """
    Compare fastest lap telemetry between two drivers.
    Returns aligned speed, throttle, brake traces and delta time.
    """
    session = load_session(year, gp, "Q")  # Qualifying for clean comparison

    def _get_tel(driver: str) -> pd.DataFrame:
        laps = session.laps.pick_driver(driver)
        lap = laps.pick_lap(lap_number) if lap_number else laps.pick_fastest()
        tel = lap.get_telemetry().add_distance()
        tel["Driver"] = driver
        return tel

    tel_a = _get_tel(driver_a)
    tel_b = _get_tel(driver_b)

    # Resample both to same distance points for comparison
    max_dist = min(tel_a["Distance"].max(), tel_b["Distance"].max())
    sample_points = np.linspace(0, max_dist, 500)

    def _resample(tel: pd.DataFrame, col: str) -> np.ndarray:
        return np.interp(sample_points, tel["Distance"].values, tel[col].values)

    speed_a = _resample(tel_a, "Speed")
    speed_b = _resample(tel_b, "Speed")
    throttle_a = _resample(tel_a, "Throttle")
    throttle_b = _resample(tel_b, "Throttle")
    brake_a = _resample(tel_a, "Brake").astype(float)
    brake_b = _resample(tel_b, "Brake").astype(float)

    delta_speed = speed_a - speed_b  # positive = A faster at that distance

    lap_time_a = float(session.laps.pick_driver(driver_a).pick_fastest()["LapTime"].total_seconds())
    lap_time_b = float(session.laps.pick_driver(driver_b).pick_fastest()["LapTime"].total_seconds())

    return {
        "distance": sample_points.tolist(),
        "driver_a": driver_a,
        "driver_b": driver_b,
        "speed_a": speed_a.tolist(),
        "speed_b": speed_b.tolist(),
        "throttle_a": throttle_a.tolist(),
        "throttle_b": throttle_b.tolist(),
        "brake_a": brake_a.tolist(),
        "brake_b": brake_b.tolist(),
        "delta_speed": delta_speed.tolist(),
        "lap_time_a": lap_time_a,
        "lap_time_b": lap_time_b,
        "gap": round(lap_time_a - lap_time_b, 3),
    }


def sector_comparison(year: int, gp: str | int,
                       drivers: list[str]) -> pd.DataFrame:
    """
    Return a DataFrame of S1/S2/S3 times for all given drivers in qualifying.
    Highlights the mini-sector best.
    """
    session = load_session(year, gp, "Q")
    rows = []
    for drv in drivers:
        laps = session.laps.pick_driver(drv)
        fastest = laps.pick_fastest()
        rows.append({
            "Driver": drv,
            "S1": fastest["Sector1Time"].total_seconds() if pd.notna(fastest["Sector1Time"]) else None,
            "S2": fastest["Sector2Time"].total_seconds() if pd.notna(fastest["Sector2Time"]) else None,
            "S3": fastest["Sector3Time"].total_seconds() if pd.notna(fastest["Sector3Time"]) else None,
            "LapTime": fastest["LapTime"].total_seconds() if pd.notna(fastest["LapTime"]) else None,
        })
    df = pd.DataFrame(rows).set_index("Driver")
    return df


def gps_speed_heatmap(year: int, gp: str | int, driver: str) -> dict:
    """
    Return GPS coordinates + speed for a driver's fastest lap,
    ready to render as a colour-coded track map.
    """
    session = load_session(year, gp, "Q")
    laps = session.laps.pick_driver(driver)
    fastest = laps.pick_fastest()
    tel = fastest.get_telemetry().add_distance()

    # fastf1 provides X/Y in rotated circuit space; convert to lat/lon approx
    x = tel["X"].values.astype(float)
    y = tel["Y"].values.astype(float)
    speed = tel["Speed"].values.astype(float)

    # Normalise to 0-1 for frontend rendering
    x_norm = (x - x.min()) / (x.max() - x.min() + 1e-9)
    y_norm = (y - y.min()) / (y.max() - y.min() + 1e-9)
    speed_norm = (speed - speed.min()) / (speed.max() - speed.min() + 1e-9)

    return {
        "driver": driver,
        "x": x_norm.tolist(),
        "y": y_norm.tolist(),
        "speed": speed.tolist(),
        "speed_norm": speed_norm.tolist(),
        "max_speed": float(speed.max()),
        "min_speed": float(speed.min()),
        "lap_time": float(fastest["LapTime"].total_seconds()),
    }


def pace_evolution(laps_df: pd.DataFrame, drivers: list[str]) -> dict:
    """
    Return lap-by-lap pace evolution for a set of drivers,
    with outliers (in/out laps, SC laps) filtered.
    """
    result = {}
    for drv in drivers:
        d_laps = laps_df[laps_df["Driver"] == drv].copy()
        # Filter: remove pit in/out laps and very slow laps (>107% of median)
        d_laps = d_laps[d_laps["PitInTime"].isna() & d_laps["PitOutTime"].isna()]
        median_lt = d_laps["LapTimeSeconds"].median()
        d_laps = d_laps[d_laps["LapTimeSeconds"] < median_lt * 1.07]
        result[drv] = {
            "laps": d_laps["LapNumber"].tolist(),
            "times": d_laps["LapTimeSeconds"].tolist(),
            "compounds": d_laps["Compound"].tolist() if "Compound" in d_laps.columns else [],
        }
    return result
