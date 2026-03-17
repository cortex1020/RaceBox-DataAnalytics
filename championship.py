"""
RaceBox — championship.py
Championship standings tracker + Monte Carlo title probability model.
Given current standings and remaining rounds, simulates the rest of the
season to produce driver/constructor title probability distributions.
"""
from __future__ import annotations
import random
from dataclasses import dataclass
import numpy as np

from data_loader import get_driver_standings, get_constructor_standings, get_event_schedule

F1_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
FASTEST_LAP_POINT = 1


@dataclass
class DriverStanding:
    code: str
    name: str
    team: str
    points: float
    wins: int
    position: int


@dataclass
class ChampionshipOutput:
    year: int
    rounds_remaining: int
    max_points_available: int
    driver_standings: list[DriverStanding]
    title_probabilities: dict[str, float]      # driver code → probability
    constructor_probabilities: dict[str, float]
    mathematically_eliminated: list[str]
    points_gap_to_leader: dict[str, float]


def parse_standings(year: int) -> tuple[list[DriverStanding], dict[str, float]]:
    """
    Fetch and parse driver standings from Ergast.
    Returns (list of DriverStanding, {team: points}).
    """
    raw = get_driver_standings(year)
    standings = []
    constructor_points: dict[str, float] = {}

    for entry in raw:
        drv = entry["Driver"]
        team = entry["Constructors"][0]["name"] if entry.get("Constructors") else "Unknown"
        pts = float(entry.get("points", 0))
        standings.append(DriverStanding(
            code=drv.get("code", drv["familyName"][:3].upper()),
            name=f"{drv['givenName']} {drv['familyName']}",
            team=team,
            points=pts,
            wins=int(entry.get("wins", 0)),
            position=int(entry.get("position", 0)),
        ))
        constructor_points[team] = constructor_points.get(team, 0) + pts

    return standings, constructor_points


def remaining_rounds(year: int, completed_rounds: int) -> int:
    schedule = get_event_schedule(year)
    return max(0, len(schedule) - completed_rounds)


def _simulate_season_remainder(standings: list[DriverStanding],
                                rounds_left: int,
                                n_sim: int = 2000) -> dict[str, float]:
    """
    Monte Carlo: simulate remaining races with uniform random results
    (weighted slightly toward current standings order as prior).
    Returns {driver_code: P(champion)}.
    """
    codes = [s.code for s in standings]
    current_pts = {s.code: s.points for s in standings}
    n = len(codes)

    # Prior weights based on current championship position
    weights = np.array([1.0 / (i + 1) for i in range(n)])
    weights = weights / weights.sum()

    champion_count = {c: 0 for c in codes}

    for _ in range(n_sim):
        sim_pts = dict(current_pts)
        for _round in range(rounds_left):
            # Random finishing order, biased toward championship order
            order = np.random.choice(codes, size=n, replace=False, p=weights)
            for pos, code in enumerate(order):
                pts = F1_POINTS[pos] if pos < len(F1_POINTS) else 0
                # Fastest lap: roughly top-5 finishers
                if pos < 5 and random.random() < 0.2:
                    pts += FASTEST_LAP_POINT
                sim_pts[code] = sim_pts.get(code, 0) + pts

        winner = max(sim_pts, key=lambda c: sim_pts[c])
        champion_count[winner] += 1

    return {c: champion_count[c] / n_sim for c in codes}


def championship_analysis(year: int, completed_rounds: int,
                           n_simulations: int = 2000) -> ChampionshipOutput:
    """
    Full championship analysis: current standings + title probability simulation.
    """
    standings, constructor_pts = parse_standings(year)
    rounds_left = remaining_rounds(year, completed_rounds)
    max_pts = rounds_left * (max(F1_POINTS) + FASTEST_LAP_POINT)

    leader_pts = standings[0].points if standings else 0
    gaps = {s.code: s.points - leader_pts for s in standings}  # negative = behind

    eliminated = [
        s.code for s in standings
        if (leader_pts - s.points) > max_pts
    ]

    # Only simulate if rounds remain
    if rounds_left > 0 and len(standings) > 1:
        title_probs = _simulate_season_remainder(standings, rounds_left, n_simulations)
        # Zero out eliminated drivers
        for code in eliminated:
            title_probs[code] = 0.0
        # Renormalise
        total = sum(title_probs.values()) or 1
        title_probs = {c: v / total for c, v in title_probs.items()}
    else:
        # Season over — winner is the leader
        title_probs = {s.code: (1.0 if i == 0 else 0.0) for i, s in enumerate(standings)}

    # Constructor probabilities — proportional to points spread
    total_c = sum(constructor_pts.values()) or 1
    constructor_probs = {t: p / total_c for t, p in constructor_pts.items()}

    return ChampionshipOutput(
        year=year,
        rounds_remaining=rounds_left,
        max_points_available=int(max_pts),
        driver_standings=standings,
        title_probabilities=title_probs,
        constructor_probabilities=constructor_probs,
        mathematically_eliminated=eliminated,
        points_gap_to_leader=gaps,
    )
