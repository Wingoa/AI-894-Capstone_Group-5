import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.middleware.cors import CORSMiddleware

from FightDataResource import FightDataResource
from cache.EventCache import EventCache
from cache.EventInfoCache import EventInfoCache
from cache.FightCache import FightCache


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent

EVENT_CSV = REPO_ROOT / "resources" / "initial_data" / "events.csv"
EVENT_INFO_CSV = REPO_ROOT / "resources" / "initial_data" / "events-info.csv"
FIGHT_CSV = REPO_ROOT / "resources" / "initial_data" / "fights.csv"


event_cache = EventCache(str(EVENT_CSV))
event_info_cache = EventInfoCache(str(EVENT_INFO_CSV))
fight_cache = FightCache(str(FIGHT_CSV))

resource = FightDataResource(event_cache, event_info_cache, fight_cache)
app = resource.app


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
