# AI-894-Capstone: Group-5

Group 5 project repo for PSU - AI 894 : Capstone Spring 2026

To run:
Create and run a virtual environment.
In venv:
cd front-end
pip install -r requirements.txt
uvicorn FrontEndResource:app --reload

---

Production Site will be hosted on Render:

https://ufc-fighter-optimizer.onrender.com/

Right now it is a static webpage, but once Jinja2 is ready, it will be hosted as
a "Web Service" on render

---

The API/Services can also be hosted on render.

The API is live here - Health Check URL

https://ai-894-capstone-group-5.onrender.com/

This will open access to the data living in our repo from the site.

Test end point - Get fights by fighter name

https://ai-894-capstone-group-5.onrender.com/fights/poirier

**API Endpoints**

- **GET /meta:** API health and dataset metadata.
- **GET /latest/{fighter_id}:** Returns the latest fight vector for a fighter (data service).
- **GET /fights/{name}:** Returns fights for a fighter by name.
- **GET /event/next:** Returns the next scheduled event's fights.
- **GET /style/{fighter_id}:** Returns the fighter style vector (prediction service).
- **GET /outcome?fighter_a_id={fighter_id}&fighter_b_id={fighter_id}:** Returns win probabilities for a fighter pair (prediction service).

Examples:

https://ai-894-capstone-group-5.onrender.com/meta

https://ai-894-capstone-group-5.onrender.com/style/c3c23c99477c041b

https://ai-894-capstone-group-5.onrender.com/outcome?fighter_a_id=b27a1fcb56a3035a&fighter_b_id=319fa1bd3176bded

Note: The prediction endpoints are served from the same API base when the model artifacts and ML dependencies are available locally or in the deployment.

---

Weekly automation

What it does: Scrapes UFC stats, runs the cleaning/vector pipeline, retrains the outcome model, and commits updated CSVs/artifacts back to the repo.

Where it runs: GitHub Actions workflow /.github/workflows/weekly_pipeline.yml (weekly)

Entrypoint: weekly_pipeline.py

Outputs: Training CSV model/fight/outcome_training_vectors.csv, vectors resources/fighter_vectors/outcome_vectors.csv, and model artifacts in model/fight/outcome_artifacts_32.
