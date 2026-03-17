"""
RaceBox — data_loader.py
Unified fetch + cache layer for fastf1, Ergast API, and OpenF1 API.
All other modules import from here — never call fastf1 or httpx directly.
"""
import os
import json
from pathlib import Path
from functools import lru_cache
from typing import Optional

import fastf1
import pandas as pd
import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

# Ergast is now maintained by Jolpica with the same response schema.
ERGAST_BASE = "https://api.jolpi.ca/ergast/f1"
OPENF1_BASE = "https://api.openf1.org/v1"

SUPPORTED_YEARS = [2024, 2025, 2026]


# ─── fastf1 helpers ────────────────────────────────────────────────────────────

def load_session(year: int, gp: str | int, session_type: str = "R") -> fastf1.core.Session:
    """Load and cache a full session (R=Race, Q=Quali, FP1/FP2/FP3)."""
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=True, weather=True, messages=True)
    return session


def get_laps(year: int, gp: str | int, session_type: str = "R") -> pd.DataFrame:
    """Return a clean laps DataFrame for a session."""
    session = load_session(year, gp, session_type)
    laps = session.laps.copy()
    laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()
    laps["Stint"] = laps.groupby("Driver")["PitOutTime"].transform(
        lambda x: (~x.isna()).cumsum()
    )
    return laps


def get_driver_telemetry(year: int, gp: str | int, driver: str, lap_number: Optional[int] = None) -> pd.DataFrame:
    """
    Return telemetry for a specific driver.
    If lap_number is None, returns their fastest lap telemetry.
    """
    session = load_session(year, gp, "R")
    driver_laps = session.laps.pick_driver(driver)
    lap = driver_laps.pick_lap(lap_number) if lap_number else driver_laps.pick_fastest()
    tel = lap.get_telemetry()
    tel["Driver"] = driver
    return tel


def get_event_schedule(year: int) -> pd.DataFrame:
    """Return the full race calendar for a season."""
    schedule = fastf1.get_event_schedule(year)
    return schedule[["RoundNumber", "EventName", "Country", "EventDate", "EventFormat"]]


def get_results(year: int, gp: str | int) -> pd.DataFrame:
    """Return race results with positions, points, fastest lap."""
    session = load_session(year, gp, "R")
    preferred = [
        "DriverNumber", "Abbreviation", "FullName", "TeamName",
        "Position", "Points", "Status", "Laps",
    ]
    cols = [c for c in preferred if c in session.results.columns]
    results = session.results[cols].copy()

    # Reconstruct fastest-lap info from lap data to keep API stable for frontend.
    fastest_driver = None
    fastest_lap_seconds = None
    try:
        fastest_lap = session.laps.pick_fastest()
        fastest_driver = fastest_lap.get("Driver")
        lap_time = fastest_lap.get("LapTime")
        if pd.notna(lap_time):
            fastest_lap_seconds = float(lap_time.total_seconds())
    except Exception:
        pass

    results["FastestLap"] = (
        results["Abbreviation"].eq(fastest_driver)
        if fastest_driver is not None
        else False
    )
    results["FastestLapTime"] = None
    if fastest_lap_seconds is not None and fastest_driver is not None:
        results.loc[results["FastestLap"], "FastestLapTime"] = float(fastest_lap_seconds)

    return results


# ─── Ergast API ─────────────────────────────────────────────────────────────────

def _ergast_get(path: str, params: dict | None = None) -> dict:
    url = f"{ERGAST_BASE}/{path}.json"
    with httpx.Client(timeout=10) as client:
        r = client.get(url, params=params or {})
        r.raise_for_status()
        return r.json()["MRData"]


def get_driver_standings(year: int) -> list[dict]:
    data = _ergast_get(f"{year}/driverStandings")
    standings = data["StandingsTable"]["StandingsLists"]
    if not standings:
        return []
    return standings[0]["DriverStandings"]


def get_constructor_standings(year: int) -> list[dict]:
    data = _ergast_get(f"{year}/constructorStandings")
    standings = data["StandingsTable"]["StandingsLists"]
    if not standings:
        return []
    return standings[0]["ConstructorStandings"]


def get_season_results(year: int) -> list[dict]:
    """All race results for a season from Ergast."""
    data = _ergast_get(f"{year}/results", params={"limit": 1000})
    return data["RaceTable"]["Races"]


def get_qualifying_results(year: int, round_num: int) -> list[dict]:
    data = _ergast_get(f"{year}/{round_num}/qualifying")
    races = data["RaceTable"]["Races"]
    return races[0]["QualifyingResults"] if races else []


# ─── OpenF1 API ─────────────────────────────────────────────────────────────────

def _openf1_get(endpoint: str, params: dict | None = None) -> list[dict]:
    url = f"{OPENF1_BASE}/{endpoint}"
    with httpx.Client(timeout=15) as client:
        r = client.get(url, params=params or {})
        r.raise_for_status()
        return r.json()


def get_live_timing(session_key: int) -> list[dict]:
    return _openf1_get("laps", {"session_key": session_key})


def get_pit_data(session_key: int) -> list[dict]:
    return _openf1_get("pit", {"session_key": session_key})


def get_weather_data(session_key: int) -> list[dict]:
    return _openf1_get("weather", {"session_key": session_key})


def get_driver_info(session_key: int) -> list[dict]:
    return _openf1_get("drivers", {"session_key": session_key})


def get_latest_session_key(year: int, gp_name: str) -> Optional[int]:
    """Resolve OpenF1 session key for a given GP name and year."""
    sessions = _openf1_get("sessions", {"year": year, "circuit_short_name": gp_name.lower()})
    race_sessions = [s for s in sessions if s.get("session_type") == "Race"]
    return race_sessions[-1]["session_key"] if race_sessions else None
