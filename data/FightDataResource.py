from fastapi import FastAPI, HTTPException, Query
import uvicorn
from cache.EventCache import EventCache
from cache.EventInfoCache import EventInfoCache
from cache.FightCache import FightCache

class FightDataResource:

    def __init__(self, eventCache: EventCache, eventInfoCache: EventInfoCache, fightCache: FightCache):
        self.app = FastAPI(title="UFC Fight Data API")
        self.eventCache = eventCache
        self.eventInfoCache = eventInfoCache
        self.fightCache = fightCache
        self._registerEndpoints()

    def run(self):
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=8000,
            reload=False,
            workers=1
        )
        print(f"Starting FightDataResource on 0.0.0.0:8000")

    def _registerEndpoints(self):

        @self.app.get("/")
        def healthCheck():
            return {
                    "status": "ok", 
                    "message": "API is running. Go to http://localhost:8080/docs for the interactive swagger page"
                    }

        @self.app.get("/fights/{name}")
        def get_fights_by_fighter(name: str):
            """
            Returns all fights where the fighter name contains the given string.
            Case-insensitive.
            """
            name_lower = name.lower()

            fights = self.fightCache.all()
            matches = []
            for fight in fights:
                for fighter in fight:
                    if name_lower in fighter.fighter.lower():
                        matches.append(fighter)


            if len(matches) == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"No fights found for fighter containing '{name}'"
                )

            return {
                    "totalMatches": len(matches),
                    "matches": matches
                }