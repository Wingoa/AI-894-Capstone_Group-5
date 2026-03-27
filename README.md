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

---

Weekly automation

What it does: Scrapes UFC stats, runs the cleaning/vector pipeline, retrains the outcome model, and commits updated CSVs/artifacts back to the repo.

Where it runs: GitHub Actions workflow /.github/workflows/weekly_pipeline.yml (weekly)

Entrypoint: weekly_pipeline.py

Outputs: Training CSV model/fight/outcome_training_vectors.csv, vectors resources/fighter_vectors/outcome_vectors.csv, and model artifacts in model/fight/outcome_artifacts_32.
