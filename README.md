# RaceBox - F1 Race Intelligence Platform

RaceBox is a full-stack Formula 1 analytics platform that combines live and historical race data, strategy modeling, Monte Carlo simulation, telemetry comparison, and championship projections.

## Features

| Module          | Description                                                          |
| --------------- | -------------------------------------------------------------------- |
| Race Wall       | Race classification, lap-time trends, DNF tracking                   |
| Strategy Engine | Tyre degradation model, pit-window analysis, undercut/overcut checks |
| Monte Carlo Sim | Win, podium, points, and position probability distributions          |
| Telemetry       | Driver-vs-driver speed/throttle/brake comparison + pace analysis     |
| Championship    | Current standings with title probability simulations                 |

## Tech Stack

- Backend: FastAPI + Uvicorn
- Data: fastf1, Jolpica Ergast-compatible API, OpenF1
- Analytics: pandas, numpy
- Frontend: single-page dashboard (`index.html` + `app.js`) with Chart.js

## Project Layout

This repository currently uses a flat layout (no `racebox/` package folder):

```text
F1-Simulator/
|- main.py
|- run.py
|- data_loader.py
|- strategy.py
|- simulator.py
|- telemetry.py
|- championship.py
|- index.html
|- app.js
|- requirements.txt
|- cache/                # auto-created fastf1 cache
```

## Setup

### 1) Create and activate a virtual environment

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

## Run

```bash
python run.py
```

Dev mode:

```bash
python run.py --reload
```

Custom port:

```bash
python run.py --port 8080
```

Open:

- Dashboard: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Key API Endpoints

```text
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

## Data Sources

- fastf1: session, laps, telemetry, weather, GPS
- Jolpica Ergast-compatible API: standings, historical race data
- OpenF1: live timing, pit, weather, session metadata

## Notes and Troubleshooting

- First-time `fastf1` session loads can download large datasets and may take time.
- Cached data is stored in `cache/` and makes repeat requests much faster.
- If you are on Ubuntu/Debian and see `externally-managed-environment`, install packages inside `.venv` (recommended) instead of system Python.
- Static dashboard script is served at `/static/app.js`.

## License

Add your preferred license file (`LICENSE`) for open-source distribution.
