"""
Weekly pipeline runner: scrape -> clean -> build outcome vectors -> optional train

Run environment: this script is intended to run from the repo root
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def run_scrape():
    logging.info("Starting one-shot scraper")

    # Make repo root importable so top-level packages like `data_model` resolve
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(DATA_DIR))
    # Change cwd so relative CSV paths in modules resolve correctly
    os.chdir(str(DATA_DIR))

    try:
        from RefreshDataService import RefreshDataService
        from scrapers.ScraperService import ScraperService
        from cache.FightCache import FightCache
        from cache.EventCache import EventCache
        from cache.EventInfoCache import EventInfoCache
    except Exception as e:
        logging.exception("Failed to import scraping modules")
        raise

    fight_csv = str(REPO_ROOT / "resources" / "initial_data" / "fights.csv")
    event_csv = str(REPO_ROOT / "resources" / "initial_data" / "events.csv")
    event_info_csv = str(REPO_ROOT / "resources" / "initial_data" / "events-info.csv")

    eventCache = EventCache(event_csv)
    eventInfoCache = EventInfoCache(event_info_csv)
    fightCache = FightCache(fight_csv)
    scraper = ScraperService()
    refresher = RefreshDataService(fightCache, eventCache, eventInfoCache, scraper)

    try:
        refresher.refreshFightData()
        refresher.reloadIncompleteData()
        logging.info("Scrape finished")
    except Exception:
        logging.exception("Scrape step failed")
        raise


def run_clean():
    logging.info("Running data cleaning pipeline")
    # run_data_clean.py handles its own cwd adjustments; call it as a script
    try:
        subprocess.check_call([sys.executable, "run_data_clean.py"], cwd=str(DATA_DIR / "clean"))
        logging.info("Cleaning finished")
    except subprocess.CalledProcessError:
        logging.exception("Data cleaning failed")
        raise


def run_style_vectors():
    logging.info("Generating outcome vectors from fight vectors")
    # Call the generator function via a -c invocation so module paths resolve from repo root
    try:
        subprocess.check_call([
            sys.executable,
            "-c",
            "from FightVectorCleaner import generateOutcomeVectorTrainingData; generateOutcomeVectorTrainingData()",
        ], cwd=str(REPO_ROOT / "model" / "style"))
        logging.info("Outcome vectors generated")
    except subprocess.CalledProcessError:
        logging.exception("Outcome vector generation failed")
        raise


def run_outcome_builder():
    logging.info("Building matchup-style training CSV")
    # Importing the module will execute the top-level builder code which writes a CSV
    try:
        subprocess.check_call([
            sys.executable,
            "-c",
            "import OutcomeVectorBuilder",
        ], cwd=str(REPO_ROOT / "model" / "fight"))
        logging.info("Outcome training table built")
    except subprocess.CalledProcessError:
        logging.exception("OutcomeVectorBuilder failed")
        raise


def run_trainer_if_available():
    # Trainer expects a CSV at model/fight/outcome_training_vectors.csv
    trainer_csv = REPO_ROOT / "model" / "fight" / "outcome_training_vectors.csv"
    if trainer_csv.exists():
        logging.info(f"Found training CSV at {trainer_csv}, starting trainer")
        try:
            subprocess.check_call([sys.executable, "OutcomeModelTrainer32.py"], cwd=str(REPO_ROOT / "model" / "fight"))
            logging.info("Training finished")
        except subprocess.CalledProcessError:
            logging.exception("Training failed")
            raise
    else:
        logging.warning(f"Training CSV not found at {trainer_csv}; skipping training step")


def main():
    try:
        run_scrape()
        run_clean()
        run_style_vectors()
        run_outcome_builder()
        run_trainer_if_available()
    except Exception:
        logging.exception("Weekly pipeline failed")
        sys.exit(1)
    logging.info("Weekly pipeline completed successfully")


if __name__ == "__main__":
    main()
