import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from fastapi.responses import PlainTextResponse

from FightDataResource import FightDataResource
from cache.EventCache import EventCache
from cache.EventInfoCache import EventInfoCache
from cache.FightCache import FightCache
from FightDataService import FightDataService
from RefreshDataService import RefreshDataService
from scrapers.ScraperService import ScraperService

# Make model subpackages importable as top-level "style" / "fight" packages
MODEL_DIR = REPO_ROOT / "model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))


EVENT_CSV = REPO_ROOT / "resources" / "initial_data" / "events.csv"
EVENT_INFO_CSV = REPO_ROOT / "resources" / "initial_data" / "events-info.csv"
FIGHT_CSV = REPO_ROOT / "resources" / "initial_data" / "fights.csv"


event_cache = EventCache(str(EVENT_CSV))
event_info_cache = EventInfoCache(str(EVENT_INFO_CSV))
fight_cache = FightCache(str(FIGHT_CSV))

fight_service = FightDataService(event_cache, event_info_cache, fight_cache)
scraper_service = ScraperService()
refresh_service = RefreshDataService(fight_cache, event_cache, event_info_cache, scraper_service)
resource = FightDataResource(fight_service, refresh_service, enable_background_refresh=False)
app = resource.app

# Register prediction endpoints with lazy model loading to reduce startup memory.
_style_service = None
_outcome_service = None
_prediction_init_error = None


def _get_prediction_services():
    global _style_service, _outcome_service, _prediction_init_error

    if _prediction_init_error is not None:
        raise RuntimeError(_prediction_init_error)

    if _style_service is not None and _outcome_service is not None:
        return _style_service, _outcome_service

    try:
        from style.StylePredictor import StylePredictor
        from style.StylePredictionService import StylePredictionService
        from fight.OutcomePredictor import OutcomePredictor
        from fight.OutcomePredictionService import OutcomePredictionService
        from client.DataApiClient import DataApiClient

        port = os.getenv("PORT", "8002")
        data_url = f"http://127.0.0.1:{port}"
        fight_style_csv = str(REPO_ROOT / "resources" / "fighter_vectors" / "fighter_style_predictions.csv")

        style_predictor = StylePredictor()
        outcome_predictor = OutcomePredictor()
        data_api_client = DataApiClient(data_url)
        _style_service = StylePredictionService(style_predictor, data_api_client,fight_style_csv)
        _outcome_service = OutcomePredictionService(outcome_predictor, _style_service, data_api_client)

        outcome_predictor = OutcomePredictor()
        data_api_client = DataApiClient(data_url)
        _outcome_service = OutcomePredictionService(outcome_predictor, _style_service, data_api_client)
        return _style_service, _outcome_service
    except Exception as e:
        _prediction_init_error = str(e)
        raise


@app.get("/style/{fighter_id}")
def get_style_prediction(fighter_id: str):
    try:
        style_service, _ = _get_prediction_services()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Prediction model unavailable: {e}")
    return style_service.getFighterStyle(fighter_id)


@app.get("/outcome")
def get_outcome_prediction(fighter_a_id: str, fighter_b_id: str):
    try:
        _, outcome_service = _get_prediction_services()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Prediction model unavailable: {e}")
    return outcome_service.predictFightFromLatest(fighter_a_id, fighter_b_id)


origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
allowed_origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]

if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Print an externally-routable URL if provided (Render sets PUBLIC_API_URL in render.yaml)
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL")
PORT = os.getenv("PORT", "8002")
if PUBLIC_API_URL:
    print(f"API public URL: {PUBLIC_API_URL}")
else:
    print(f"API listening on 0.0.0.0:{PORT} (set PUBLIC_API_URL to show the external URL)")


@app.get("/meta")
def get_meta():
    def file_meta(path: Path):
        if not path.exists():
            return {
                "path": str(path.relative_to(REPO_ROOT)),
                "exists": False,
                "sizeBytes": 0,
                "lastModifiedUtc": None,
            }

        stat_result = path.stat()
        return {
            "path": str(path.relative_to(REPO_ROOT)),
            "exists": True,
            "sizeBytes": stat_result.st_size,
            "lastModifiedUtc": datetime.fromtimestamp(
                stat_result.st_mtime,
                tz=timezone.utc,
            ).isoformat(),
        }

    return {
        "status": "ok",
        "datasets": {
            "events": file_meta(EVENT_CSV),
            "eventInfo": file_meta(EVENT_INFO_CSV),
            "fights": file_meta(FIGHT_CSV),
        },
        "counts": {
            "events": len(event_cache.all()),
            "eventInfoGroups": len(event_info_cache.all()),
            "fightGroups": len(fight_cache.all()),
        },
    }


@app.head("/health")
@app.get("/health")
def health() -> PlainTextResponse:
    """Lightweight health check for uptime monitors (responds to HEAD/GET)."""
    return PlainTextResponse("OK", status_code=200)
