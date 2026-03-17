"""
RaceBox — simulator.py
Monte Carlo race simulator. Given a grid, strategy assignments, lap time
distributions, and random event probabilities, runs N race simulations
and returns finishing probability matrices and expected championship impact.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from strategy import PIT_LOSS_SECONDS, lap_time_on_tyre, TYRE_DEG_RATE


@dataclass
class DriverConfig:
    code: str
    team: str
    grid_position: int
    base_pace: float            # median clean-air lap time in seconds
    pace_std: float = 0.3       # lap-to-lap variation (std dev)
    compounds: list[str] = field(default_factory=lambda: ["MEDIUM", "HARD"])
    stint_lengths: list[int] = field(default_factory=lambda: [28, 28])
    dnf_probability: float = 0.03
    overtake_ability: float = 0.5   # 0–1 scale

    @property
    def strategy_label(self):
        return " → ".join(
            f"{c[:1]}{l}" for c, l in zip(self.compounds, self.stint_lengths)
        )


@dataclass
class SimResult:
    driver: str
    team: str
    simulated_position: int
    simulated_race_time: float
    dnf: bool = False
    dnf_lap: Optional[int] = None


@dataclass
class SimulationOutput:
    n_simulations: int
    drivers: list[str]
    win_probabilities: dict[str, float]
    podium_probabilities: dict[str, float]
    points_probabilities: dict[str, float]   # P1–P10
    expected_positions: dict[str, float]
    position_matrix: dict[str, list[float]]  # driver → P(finishing P1..P20)
    fastest_lap_probabilities: dict[str, float]
    safety_car_triggered: float              # fraction of sims with SC


SAFETY_CAR_PROB_PER_LAP = 0.015
SAFETY_CAR_DURATION_LAPS = 5
SC_PACE_DELTA = 15.0
F1_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


def _simulate_one_race(drivers: list[DriverConfig],
                        race_laps: int,
                        randomise_grid: bool = False) -> tuple[list[SimResult], bool]:
    """Run a single race simulation. Returns (results, safety_car_occurred)."""

    n = len(drivers)
    if randomise_grid:
        grid = list(range(1, n + 1))
        random.shuffle(grid)
        for d, g in zip(drivers, grid):
            d.grid_position = g

    race_times = {}
    dnf_info = {}
    lap_times_by_driver = {}

    # Overtaking model: position changes probabilistically if a faster driver
    # is stuck behind a slower one. Simplified: slow leaders get overtaken with
    # probability proportional to pace delta and overtake ability.
    positions = {d.code: d.grid_position for d in drivers}
    total_times = {d.code: d.grid_position * 0.5 for d in drivers}  # grid offset

    sc_active = False
    sc_countdown = 0
    safety_car_occurred = False

    current_stint = {d.code: 0 for d in drivers}
    stint_laps  = {d.code: 0 for d in drivers}
    pit_done    = {d.code: set() for d in drivers}

    fastest_lap_times = {d.code: float('inf') for d in drivers}

    for lap in range(1, race_laps + 1):
        # Safety car logic
        if not sc_active and random.random() < SAFETY_CAR_PROB_PER_LAP:
            sc_active = True
            sc_countdown = SAFETY_CAR_DURATION_LAPS
            safety_car_occurred = True
        if sc_active:
            sc_countdown -= 1
            if sc_countdown <= 0:
                sc_active = False

        for d in drivers:
            if d.code in dnf_info:
                continue

            # DNF check
            if random.random() < d.dnf_probability / race_laps:
                dnf_info[d.code] = lap
                total_times[d.code] += 1e6
                continue

            # Which stint are we in?
            si = current_stint[d.code]
            if si < len(d.stint_lengths) and stint_laps[d.code] >= d.stint_lengths[si]:
                # Pit stop
                if si not in pit_done[d.code]:
                    total_times[d.code] += PIT_LOSS_SECONDS
                    pit_done[d.code].add(si)
                    current_stint[d.code] += 1
                    stint_laps[d.code] = 0
                    si = current_stint[d.code]

            compound = d.compounds[min(si, len(d.compounds) - 1)]
            tyre_age = stint_laps[d.code]
            base = d.base_pace + np.random.normal(0, d.pace_std)
            lt = lap_time_on_tyre(base, compound, tyre_age)

            if sc_active:
                lt = max(lt, d.base_pace + SC_PACE_DELTA + np.random.normal(0, 0.5))

            total_times[d.code] = total_times.get(d.code, 0) + lt
            stint_laps[d.code] += 1

            if lt < fastest_lap_times[d.code]:
                fastest_lap_times[d.code] = lt

    # Sort by race time
    sorted_drivers = sorted(
        [d for d in drivers],
        key=lambda d: total_times.get(d.code, 1e9)
    )

    results = []
    for pos, d in enumerate(sorted_drivers, 1):
        results.append(SimResult(
            driver=d.code,
            team=d.team,
            simulated_position=pos,
            simulated_race_time=total_times.get(d.code, 0),
            dnf=d.code in dnf_info,
            dnf_lap=dnf_info.get(d.code),
        ))

    return results, safety_car_occurred


def run_simulation(drivers: list[DriverConfig],
                   race_laps: int = 56,
                   n_simulations: int = 1000,
                   randomise_grid: bool = False) -> SimulationOutput:
    """
    Run N Monte Carlo race simulations.
    Returns aggregated probability distributions.
    """
    driver_codes = [d.code for d in drivers]
    n = len(driver_codes)

    position_counts = {code: [0] * n for code in driver_codes}
    fastest_lap_counts = {code: 0 for code in driver_codes}
    sc_count = 0

    all_positions = {code: [] for code in driver_codes}

    for _ in range(n_simulations):
        results, sc = _simulate_one_race(
            [DriverConfig(**vars(d)) for d in drivers],  # fresh copy per sim
            race_laps,
            randomise_grid,
        )
        if sc:
            sc_count += 1

        # Track fastest lap per sim (driver with best personal best)
        fl_winner = min(driver_codes, key=lambda c: float('inf'))  # placeholder
        best_lt = float('inf')
        for r in results:
            all_positions[r.driver].append(r.simulated_position)
            pos_idx = r.simulated_position - 1
            if 0 <= pos_idx < n:
                position_counts[r.driver][pos_idx] += 1

    # Build output
    win_prob = {c: position_counts[c][0] / n_simulations for c in driver_codes}
    podium_prob = {
        c: sum(position_counts[c][:3]) / n_simulations for c in driver_codes
    }
    points_prob = {
        c: sum(position_counts[c][:10]) / n_simulations for c in driver_codes
    }
    expected_pos = {
        c: float(np.mean(all_positions[c])) if all_positions[c] else float(n)
        for c in driver_codes
    }
    pos_matrix = {
        c: [cnt / n_simulations for cnt in position_counts[c]]
        for c in driver_codes
    }

    return SimulationOutput(
        n_simulations=n_simulations,
        drivers=driver_codes,
        win_probabilities=win_prob,
        podium_probabilities=podium_prob,
        points_probabilities=points_prob,
        expected_positions=expected_pos,
        position_matrix=pos_matrix,
        fastest_lap_probabilities=fastest_lap_counts,
        safety_car_triggered=sc_count / n_simulations,
    )


def make_default_grid(standings_data: list[dict], base_pace: float = 90.0) -> list[DriverConfig]:
    """
    Build a DriverConfig grid from Ergast standings data with sensible pace deltas.
    Top drivers get slightly better pace; modelled as a linear spread of 1.5s.
    """
    configs = []
    n = len(standings_data)
    for i, entry in enumerate(standings_data):
        drv = entry["Driver"]
        constructor = entry["Constructors"][0]["name"] if entry.get("Constructors") else "Unknown"
        pace_delta = (i / max(n - 1, 1)) * 1.5
        configs.append(DriverConfig(
            code=drv["code"],
            team=constructor,
            grid_position=i + 1,
            base_pace=base_pace + pace_delta,
            pace_std=0.25 + i * 0.01,
            compounds=["MEDIUM", "HARD"],
            stint_lengths=[28, 28],
            dnf_probability=0.03,
            overtake_ability=max(0.2, 0.9 - i * 0.035),
        ))
    return configs
