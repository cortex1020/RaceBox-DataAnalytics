"""
RaceBox — api/main.py
FastAPI application exposing all RaceBox modules via REST endpoints.
Run with: uvicorn racebox.api.main:app --reload --port 8000
"""
from __future__ import annotations
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import traceback

import data_loader as dl
import strategy as strat
import simulator as sim
import telemetry as tel
import championship as champ

app = FastAPI(
    title="RaceBox API",
    description="F1 race intelligence platform — strategy, simulation, telemetry, championship",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")


# ─── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def serve_dashboard():
    return FileResponse(str(DASHBOARD_DIR / "index.html"))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# ─── Schedule ───────────────────────────────────────────────────────────────────

@app.get("/api/schedule/{year}")
async def get_schedule(year: int):
    try:
        schedule = dl.get_event_schedule(year)
        return schedule.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Race results ────────────────────────────────────────────────────────────────

@app.get("/api/race/{year}/{gp}/results")
async def get_race_results(year: int, gp: str):
    try:
        gp_key = int(gp) if gp.isdigit() else gp
        results = dl.get_results(year, gp_key)
        return results.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/race/{year}/{gp}/laps")
async def get_race_laps(year: int, gp: str,
                         driver: Optional[str] = None):
    try:
        gp_key = int(gp) if gp.isdigit() else gp
        laps = dl.get_laps(year, gp_key)
        if driver:
            laps = laps[laps["Driver"] == driver.upper()]
        return laps[["Driver", "LapNumber", "LapTimeSeconds", "Compound",
                      "TyreLife", "Stint", "PitInTime"]].fillna("").to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Strategy ────────────────────────────────────────────────────────────────────

class StrategyRequest(BaseModel):
    race_laps: int = 56
    base_lap_time: float = 90.5
    compounds: Optional[list[list[str]]] = None
    stint_lengths: Optional[list[list[int]]] = None


@app.post("/api/strategy/compare")
async def compare_strategies(req: StrategyRequest):
    try:
        candidates = None
        if req.compounds and req.stint_lengths:
            candidates = list(zip(req.compounds, req.stint_lengths))
        strategies = strat.compare_strategies(req.race_laps, req.base_lap_time, candidates)
        return [
            {
                "label": s.label,
                "total_race_time": round(s.total_race_time, 2),
                "pit_stops": s.pit_stops,
                "stints": [
                    {
                        "compound": st.compound,
                        "start_lap": st.start_lap,
                        "end_lap": st.end_lap,
                        "avg_lap_time": round(st.avg_lap_time, 3),
                        "length": st.length,
                    }
                    for st in s.stints
                ],
            }
            for s in strategies[:20]  # top 20
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategy/undercut/{year}/{gp}")
async def undercut_analysis(year: int, gp: str,
                              attacker: str = Query(...),
                              defender: str = Query(...),
                              current_lap: int = Query(30)):
    try:
        gp_key = int(gp) if gp.isdigit() else gp
        laps = dl.get_laps(year, gp_key)
        result = strat.undercut_analysis(laps, attacker.upper(), defender.upper(), current_lap)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Simulation ──────────────────────────────────────────────────────────────────

class SimRequest(BaseModel):
    year: int = 2024
    race_laps: int = 56
    n_simulations: int = 500
    drivers: Optional[list[dict]] = None


@app.post("/api/simulate")
async def simulate_race(req: SimRequest):
    try:
        if req.drivers:
            grid = [sim.DriverConfig(**d) for d in req.drivers]
        else:
            standings = dl.get_driver_standings(req.year)
            grid = sim.make_default_grid(standings[:20])

        output = sim.run_simulation(grid, req.race_laps, req.n_simulations)
        return {
            "n_simulations": output.n_simulations,
            "safety_car_probability": round(output.safety_car_triggered, 3),
            "drivers": [
                {
                    "driver": code,
                    "win_probability": round(output.win_probabilities[code], 4),
                    "podium_probability": round(output.podium_probabilities[code], 4),
                    "points_probability": round(output.points_probabilities[code], 4),
                    "expected_position": round(output.expected_positions[code], 2),
                    "position_distribution": [
                        round(p, 4) for p in output.position_matrix[code]
                    ],
                }
                for code in output.drivers
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=traceback.format_exc())


# ─── Telemetry ───────────────────────────────────────────────────────────────────

@app.get("/api/telemetry/{year}/{gp}/compare")
async def telemetry_compare(year: int, gp: str,
                              driver_a: str = Query(...),
                              driver_b: str = Query(...)):
    try:
        gp_key = int(gp) if gp.isdigit() else gp
        data = tel.compare_drivers_telemetry(year, gp_key, driver_a.upper(), driver_b.upper())
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/telemetry/{year}/{gp}/heatmap")
async def track_heatmap(year: int, gp: str, driver: str = Query(...)):
    try:
        gp_key = int(gp) if gp.isdigit() else gp
        data = tel.gps_speed_heatmap(year, gp_key, driver.upper())
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/telemetry/{year}/{gp}/sectors")
async def sector_times(year: int, gp: str,
                        drivers: str = Query(..., description="Comma-separated driver codes")):
    try:
        gp_key = int(gp) if gp.isdigit() else gp
        driver_list = [d.strip().upper() for d in drivers.split(",")]
        df = tel.sector_comparison(year, gp_key, driver_list)
        return df.reset_index().to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/telemetry/{year}/{gp}/pace")
async def pace_evolution(year: int, gp: str,
                          drivers: str = Query(...)):
    try:
        gp_key = int(gp) if gp.isdigit() else gp
        driver_list = [d.strip().upper() for d in drivers.split(",")]
        laps = dl.get_laps(year, gp_key)
        data = tel.pace_evolution(laps, driver_list)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Championship ────────────────────────────────────────────────────────────────

@app.get("/api/championship/{year}")
async def championship(year: int,
                        completed_rounds: int = Query(0),
                        n_simulations: int = Query(1000)):
    try:
        result = champ.championship_analysis(year, completed_rounds, n_simulations)
        return {
            "year": result.year,
            "rounds_remaining": result.rounds_remaining,
            "max_points_available": result.max_points_available,
            "standings": [
                {
                    "position": s.position,
                    "code": s.code,
                    "name": s.name,
                    "team": s.team,
                    "points": s.points,
                    "wins": s.wins,
                    "title_probability": round(result.title_probabilities.get(s.code, 0), 4),
                    "points_gap": round(result.points_gap_to_leader.get(s.code, 0), 1),
                    "eliminated": s.code in result.mathematically_eliminated,
                }
                for s in result.driver_standings
            ],
            "constructor_standings": [
                {
                    "team": team,
                    "probability": round(prob, 4),
                }
                for team, prob in sorted(
                    result.constructor_probabilities.items(),
                    key=lambda x: -x[1]
                )
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Ergast raw ──────────────────────────────────────────────────────────────────

@app.get("/api/standings/drivers/{year}")
async def driver_standings(year: int):
    try:
        return dl.get_driver_standings(year)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/standings/constructors/{year}")
async def constructor_standings(year: int):
    try:
        return dl.get_constructor_standings(year)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
