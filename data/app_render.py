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
from fastapi.responses import PlainTextResponse

from FightDataResource import FightDataResource
from cache.EventCache import EventCache
from cache.EventInfoCache import EventInfoCache
from cache.FightCache import FightCache
from FightDataService import FightDataService

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
resource = FightDataResource(fight_service)
app = resource.app

# Register prediction endpoints on the same app so /outcome and /style are available
try:
    from PredictionResource import PredictionResource
    from style.StylePredictor import StylePredictor
    from style.StylePredictionService import StylePredictionService
    from fight.OutcomePredictor import OutcomePredictor
    from fight.OutcomePredictionService import OutcomePredictionService
    from client.DataApiClient import DataApiClient

    # Build services with artifacts/CSV paths relative to the repo
    PORT = os.getenv("PORT", "8002")
    data_url = f"http://127.0.0.1:{PORT}"

    fight_style_csv = str(REPO_ROOT / "resources" / "fighter_vectors" / "fighter_style_predictions.csv")

    style_predictor = StylePredictor()
    style_service = StylePredictionService(style_predictor, fight_style_csv)

    outcome_predictor = OutcomePredictor()
    data_api_client = DataApiClient(data_url)
    outcome_service = OutcomePredictionService(outcome_predictor, style_service, data_api_client)

    # Instantiate PredictionResource using the existing app so routes are mounted at root
    PredictionResource(style_service, outcome_service, app=app)
except Exception as e:
    print(f"Warning: could not register PredictionResource routes: {e}")
    # If prediction services couldn't be instantiated (missing ML deps or artifacts),
    # register stub endpoints so the routes exist and return a clear 503 error.
    from fastapi import HTTPException

    @app.get("/style/{fighter_id}")
    def _style_unavailable(fighter_id: str):
        raise HTTPException(status_code=503, detail="Prediction model unavailable: missing dependencies or artifacts")

    @app.get("/outcome")
    def _outcome_unavailable(fighter_a_id: str, fighter_b_id: str):
        raise HTTPException(status_code=503, detail="Prediction model unavailable: missing dependencies or artifacts")


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
