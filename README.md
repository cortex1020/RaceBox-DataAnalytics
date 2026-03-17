# RaceBox — F1 Race Intelligence Platform

A full-stack F1 data platform combining real race data, strategy modelling,
Monte Carlo simulation, and driver telemetry. Feels like running a pit wall.

## Features

| Module | What it does |
|---|---|
| **Race Wall** | Full race classification, lap time charts, DNF tracker |
| **Strategy Engine** | Tyre degradation model, optimal pit windows, undercut/overcut analysis |
| **Monte Carlo Sim** | Run N race simulations, get win/podium/points probability distributions |
| **Telemetry** | Head-to-head speed traces, throttle/brake, sector times, GPS heatmap |
| **Championship** | Live standings + title probability simulation for 2024 & 2025 |

## Setup

```bash
cd racebox
pip install -r requirements.txt
```

## Running

```bash
# From the project root (one level above racebox/)
python -m racebox.run

# Or from inside racebox/
python run.py

# Dev mode (hot reload)
python run.py --reload

# Custom port
python run.py --port 8080
```

Then open **http://localhost:8000** in your browser.

API documentation is auto-generated at **http://localhost:8000/docs**

## Project structure

```
racebox/
├── run.py                    # Entry point
├── requirements.txt
├── core/
│   ├── data_loader.py        # fastf1 + Ergast + OpenF1 unified fetch layer
│   ├── strategy.py           # Tyre model, stint builder, undercut analysis
│   ├── simulator.py          # Monte Carlo race engine
│   ├── telemetry.py          # Driver comparison, GPS heatmap
│   └── championship.py       # Standings + title probability
├── api/
│   └── main.py               # FastAPI app with all REST endpoints
├── dashboard/
│   ├── index.html            # Single-page race control dashboard
│   └── static/
│       └── js/app.js         # All dashboard logic + Chart.js renders
└── cache/                    # fastf1 session cache (auto-populated)
```

## Key API endpoints

```
GET  /api/schedule/{year}
GET  /api/race/{year}/{gp}/results
GET  /api/race/{year}/{gp}/laps
POST /api/strategy/compare
GET  /api/strategy/undercut/{year}/{gp}?attacker=VER&defender=NOR&current_lap=30
POST /api/simulate
GET  /api/telemetry/{year}/{gp}/compare?driver_a=VER&driver_b=NOR
GET  /api/telemetry/{year}/{gp}/heatmap?driver=VER
GET  /api/telemetry/{year}/{gp}/sectors?drivers=VER,NOR,HAM
GET  /api/championship/{year}?completed_rounds=10
GET  /api/standings/drivers/{year}
GET  /api/standings/constructors/{year}
```

## Data sources

- **fastf1** — lap times, telemetry, tyre data, GPS (local cache after first load)
- **Ergast API** — race results, standings, historical data
- **OpenF1 API** — live timing, pit data, weather (for current season)

## Notes

- First load of a session downloads ~50–200MB via fastf1 and caches it locally
- Subsequent loads are near-instant from cache
- 2025 data only available for completed rounds
- Monte Carlo sim with 1000 iterations takes ~2–5 seconds
- Strategy comparison auto-generates ~500+ candidate strategies
