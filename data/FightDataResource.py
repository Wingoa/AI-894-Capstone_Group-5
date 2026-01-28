from fastapi import FastAPI, HTTPException, Query

import ScraperService

app = FastAPI(title="UFC Fight Data API")

@app.get("/fights/{name}")
def get_fights_by_fighter(name: str):
    """
    Returns all fights where the fighter name contains the given string.
    Case-insensitive.
    """
    name_lower = name.lower()

    df = ScraperService.loadFights()
    matches = df[
        df["fighter"].str.lower().str.contains(name_lower, na=False)
    ]

    if matches.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No fights found for fighter containing '{name}'"
        )

    return matches.to_dict(orient="records")