# AI-894-Capstone: Group-5

Group 5 project repo for PSU - AI 894 : Capstone Spring 2026

Local Run Commands (macOS)

Prerequisites:

    # macOS (optional)
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    brew install python

Create and activate a virtualenv (repo root):

    python3 -m venv .venv
    source .venv/bin/activate        # bash / zsh
    # or: . .venv/bin/activate
    # fish: source .venv/bin/activate.fish

Install dependencies:

    pip install -r requirements.txt
    # or install only parts:
    pip install -r requirements-api.txt
    pip install -r requirements-frontend.txt

Set Python path (repo root):

    export PYTHONPATH=".:data"

Run the API (Terminal 1, repo root):

    source .venv/bin/activate
    export PYTHONPATH=".:data"
    python -m uvicorn data.app_render:app --reload --port 8002

Run the Front-end (Terminal 2):

    cd front-end
    source ../.venv/bin/activate
    export PREDICTION_SERVICE_URL="http://127.0.0.1:8002"
    export DATA_SERVICE_URL="http://127.0.0.1:8002"
    python -m uvicorn FrontEndResource:app --reload --port 8001

One-line front-end (temporary envs):

    PREDICTION_SERVICE_URL="http://127.0.0.1:8002" DATA_SERVICE_URL="http://127.0.0.1:8002" python -m uvicorn FrontEndResource:app --reload --port 8001

Notes:
- Use `export VAR=...` on bash/zsh, `set -x` on fish, and PowerShell syntax only on Windows.
- README contains Windows commands for Windows; ignore them on macOS.
- If you see import errors, confirm `export PYTHONPATH=".:data"` was run in the same shell as `uvicorn`.
- To stop, press Ctrl+C in the terminal running `uvicorn`.

<br>
<hr>
<br>

**Production Site**

https://ufc-fighter-optimizer.onrender.com/

The site is hosted as a "Web Service" on Render

<br>
<hr>
<br>

**Production API**

The API is live here - Health Check URL

https://ai-894-capstone-group-5.onrender.com/

This will open access to the data living in our repo from the site.

Test end point - Get fights by fighter name

https://ai-894-capstone-group-5.onrender.com/fights/poirier

**API Endpoints**

- **GET /meta:** API health and dataset metadata.

- **GET /meta:** API health and dataset metadata.
- **GET /health** / **HEAD /health:** Lightweight health check for uptime monitors — responds 200 quickly. Use this for uptime pings.
- **GET /latest/{fighter_id}:** Returns the latest fight vector for a fighter (data service).
- **GET /fights/{name}:** Returns fights for a fighter by name.
- **GET /event/next:** Returns the next scheduled event's fights.
- **GET /style/{fighter_id}:** Returns the fighter style vector (prediction service).
- **GET /outcome?fighter_a_id={fighter_id}&fighter_b_id={fighter_id}:** Returns win probabilities for a fighter pair (prediction service).

**Front-end health**

- **GET /health** / **HEAD /health:** Front-end lightweight health check (use this to keep the web service awake).

Examples:

https://ai-894-capstone-group-5.onrender.com/meta

https://ai-894-capstone-group-5.onrender.com/style/c3c23c99477c041b

https://ai-894-capstone-group-5.onrender.com/outcome?fighter_a_id=b27a1fcb56a3035a&fighter_b_id=319fa1bd3176bded

Note: The prediction endpoints are served from the same API base when the model artifacts and ML dependencies are available locally or in the deployment.

<br>
<hr>
<br>

**Weekly automation**

What it does: Scrapes UFC stats, runs the cleaning/vector pipeline, retrains the outcome model, and commits updated CSVs/artifacts back to the repo.

Where it runs: GitHub Actions workflow /.github/workflows/weekly_pipeline.yml (weekly)

Entrypoint: weekly_pipeline.py

Outputs: Training CSV model/fight/outcome_training_vectors.csv, vectors resources/fighter_vectors/outcome_vectors.csv, and model artifacts in model/fight/outcome_artifacts_32.
