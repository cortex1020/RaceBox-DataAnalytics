"""
RaceBox — strategy.py
Tyre degradation models, optimal pit windows, undercut / overcut analysis,
and multi-stop strategy comparison. All functions take pre-loaded DataFrames
from data_loader so they can be used offline (no re-fetch).
"""
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

TYRE_BASE_PACE = {
    "SOFT":   0.0,
    "MEDIUM": 0.4,
    "HARD":   0.9,
    "INTER":  1.5,
    "WET":    2.5,
}
TYRE_DEG_RATE = {
    "SOFT":   0.085,
    "MEDIUM": 0.045,
    "HARD":   0.022,
    "INTER":  0.060,
    "WET":    0.035,
}
PIT_LOSS_SECONDS = 22.0


@dataclass
class Stint:
    compound: str
    start_lap: int
    end_lap: int
    avg_lap_time: float = 0.0
    deg_per_lap: float = 0.0

    @property
    def length(self) -> int:
        return self.end_lap - self.start_lap + 1


@dataclass
class Strategy:
    stints: list[Stint]
    total_race_time: float = 0.0
    pit_stops: int = 0
    label: str = ""


# ─── Tyre model ─────────────────────────────────────────────────────────────────

def lap_time_on_tyre(base_lap: float, compound: str, tyre_age: int) -> float:
    """Estimate a lap time given compound and tyre age in laps."""
    base_delta = TYRE_BASE_PACE.get(compound, 1.0)
    deg = TYRE_DEG_RATE.get(compound, 0.05)
    return base_lap + base_delta + (deg * tyre_age ** 1.12)


def fit_deg_model(laps_df: pd.DataFrame, driver: str, compound: str) -> dict:
    """
    Fit a per-driver degradation model from real lap data.
    Returns dict with {slope, intercept, r2, sample_size}.
    """
    mask = (laps_df["Driver"] == driver) & (laps_df["Compound"] == compound)
    stint_laps = laps_df[mask].dropna(subset=["LapTimeSeconds", "TyreLife"])

    if len(stint_laps) < 3:
        return {"slope": TYRE_DEG_RATE.get(compound, 0.05),
                "intercept": 0.0, "r2": 0.0, "sample_size": 0}

    x = stint_laps["TyreLife"].values.reshape(-1, 1)
    y = stint_laps["LapTimeSeconds"].values

    from numpy.polynomial import polynomial as P
    coeffs = np.polyfit(x.ravel(), y, 1)
    y_pred = np.polyval(coeffs, x.ravel())
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return {
        "slope": float(coeffs[0]),
        "intercept": float(coeffs[1]),
        "r2": float(r2),
        "sample_size": len(stint_laps),
    }


# ─── Strategy builder ───────────────────────────────────────────────────────────

def build_strategy(compounds: list[str], stint_lengths: list[int],
                   base_lap_time: float) -> Strategy:
    """
    Construct a Strategy object from a list of compounds + stint lengths.
    Calculates total race time including pit stop losses.
    """
    assert len(compounds) == len(stint_lengths), "Compound and stint length lists must match"
    stints = []
    total_time = 0.0
    lap = 1

    for i, (compound, length) in enumerate(zip(compounds, stint_lengths)):
        stint_time = sum(
            lap_time_on_tyre(base_lap_time, compound, age)
            for age in range(length)
        )
        deg = TYRE_DEG_RATE.get(compound, 0.05)
        stints.append(Stint(
            compound=compound,
            start_lap=lap,
            end_lap=lap + length - 1,
            avg_lap_time=stint_time / length,
            deg_per_lap=deg,
        ))
        total_time += stint_time
        if i < len(compounds) - 1:
            total_time += PIT_LOSS_SECONDS
        lap += length

    label = " → ".join(f"{c[:1]}{l}" for c, l in zip(compounds, stint_lengths))
    return Strategy(
        stints=stints,
        total_race_time=total_time,
        pit_stops=len(compounds) - 1,
        label=label,
    )


def compare_strategies(race_laps: int, base_lap_time: float,
                        candidates: list[tuple[list[str], list[int]]] | None = None
                        ) -> list[Strategy]:
    """
    Compare a set of strategy candidates and return sorted by total race time.
    If candidates is None, generates common 1-stop and 2-stop combos automatically.
    """
    if candidates is None:
        candidates = _generate_candidates(race_laps)

    strategies = []
    for compounds, lengths in candidates:
        if sum(lengths) != race_laps:
            continue
        strat = build_strategy(compounds, lengths, base_lap_time)
        strategies.append(strat)

    return sorted(strategies, key=lambda s: s.total_race_time)


def _generate_candidates(race_laps: int) -> list[tuple[list[str], list[int]]]:
    """Auto-generate plausible 1-stop and 2-stop strategies for a given race distance."""
    cands = []
    compounds = ["SOFT", "MEDIUM", "HARD"]

    for c1 in compounds:
        for c2 in compounds:
            if c1 == c2:
                continue
            for split in range(15, race_laps - 15, 5):
                cands.append(([c1, c2], [split, race_laps - split]))

    for c1 in compounds:
        for c2 in compounds:
            for c3 in compounds:
                if c1 == c2 == c3:
                    continue
                for s1 in range(12, 25, 4):
                    for s2 in range(12, 25, 4):
                        s3 = race_laps - s1 - s2
                        if s3 > 10:
                            cands.append(([c1, c2, c3], [s1, s2, s3]))
    return cands


# ─── Undercut / overcut analysis ────────────────────────────────────────────────

def undercut_analysis(laps_df: pd.DataFrame,
                      attacker: str, defender: str,
                      current_lap: int) -> dict:
    """
    Estimate whether an undercut by the attacker is viable against the defender.
    Returns gap projections and recommendation.
    """
    def _avg_pace(driver: str, n: int = 5) -> float:
        recent = laps_df[laps_df["Driver"] == driver].tail(n)
        return recent["LapTimeSeconds"].mean()

    att_pace = _avg_pace(attacker)
    def_pace = _avg_pace(defender)
    gap_col = laps_df[laps_df["Driver"] == attacker].tail(1)
    current_gap = float(gap_col["Time"].dt.total_seconds().values[0]) if not gap_col.empty else 5.0

    soft_advantage = TYRE_BASE_PACE["MEDIUM"] - TYRE_BASE_PACE["SOFT"]
    laps_to_make_up = PIT_LOSS_SECONDS / max(soft_advantage - (def_pace - att_pace), 0.01)

    viable = laps_to_make_up < 15 and current_gap < PIT_LOSS_SECONDS * 1.2

    return {
        "attacker": attacker,
        "defender": defender,
        "current_gap_s": round(current_gap, 3),
        "pit_loss_s": PIT_LOSS_SECONDS,
        "soft_advantage_per_lap": round(soft_advantage, 3),
        "laps_to_recover": round(laps_to_make_up, 1),
        "undercut_viable": viable,
        "recommendation": "PIT NOW — undercut viable" if viable else "Stay out — overcut or track position",
    }
