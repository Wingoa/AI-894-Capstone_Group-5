# Copilot Instructions for AI-894 Capstone: UFC Fighter Optimizer Dashboard

## Project Overview

**Long-term goal**: Build an AI-driven dashboard for style matchup analysis and coaching recommendations. Fighters exhibit distinct styles (striking, muay thai, wrestling, grappling, pace) that interact non-linearly; the system predicts exploitable patterns and suggests tactical adjustments.

**Current focus**: Data collection and caching layer. This project scrapes UFC fight statistics from ufcstats.com, persists them append-only in CSVs, and serves them via a FastAPI. The data pipeline feeds downstream ML models (XGBoost, NMF, SHAP) and the Streamlit dashboard (future deliverable).

**Architecture**: Three-layer separation—**scrapers** (external HTTP → BeautifulSoup parsing), **cache** (in-memory + CSV persistence), **API** (FastAPI endpoints).

## Architecture & Data Flow

### Core Pattern: Layered Caching

The project uses a **generic CSV-backed cache** pattern defined in [cache/BaseCsvCache.py](../data/cache/BaseCsvCache.py):

- **Load**: Lazy-load CSV on first access, cache in-memory with thread-safe locks (RLock)
- **Persist**: Append new records to CSV via `append_to_csv()` (never overwrite)
- **Query**: In-memory lookups via key or `all()`

**Subclasses implement**:

- `key_of(value)`: Extract unique key from domain object
- `_load_from_csv()`: Parse CSV rows into typed objects (dataclasses)
- `append_to_csv()`: Serialize object to CSV row

Example: [FightCache.py](../data/cache/FightCache.py) stores `List[FightStatLine]` per fight_id (fights have 2 rows—one per fighter).

### Data Entities

- **Events**: High-level UFC event info (date, name, event_id)
- **EventInfo**: Per-event details, links to individual fights (event_info.csv has multiple rows per event)
- **Fights**: Fight statistics—knockdowns, strikes, takedowns, etc. (fights.csv: 2 rows per fight, one per fighter)

### Refresh Workflow

[ScraperService.refreshFightData()](../data/ScraperService.py):

1. Scrape new events from ufcstats.com
2. Detect new event_ids (delta against cached events)
3. For each new event: scrape EventInfo → find fight_ids → scrape fight statistics
4. Persist each layer before moving to next (Events → EventInfo → Fights)

**Why append-only design**: Data persists even if code crashes mid-import; enables reproducible re-processing. The CSV format allows downstream models to time-split by event date (train ≤ 2025, test > 2025).

## Code Patterns & Conventions

### Scraper Pattern

Scrapers in [scrapers/](../data/scrapers/) handle HTTP + parsing:

- Use `ScraperUtil.make_session()` for requests with proper browser headers (avoids 502 errors)
- Use `BeautifulSoup` with CSS selectors; `find_table_by_headers()` finds tables by thead content
- Helper: `two_vals_from_td()` extracts both fighters' stats from shared `<td>` cells
- Return `List[Dict]` or typed lists; scrapers do NOT persist directly

### API Pattern

[FightDataResource.py](../data/FightDataResource.py) exposes FastAPI endpoints:

- Import `ScraperService` and call loader methods (e.g., `ScraperService.loadFights()`)
- Return pandas DataFrames as `to_dict(orient="records")`
- Use pandas filtering for queries (case-insensitive example: `.str.lower().str.contains()`)

### CSV Format

- All CSVs in [resources/](../resources/): fights.csv, events.csv, events-info.csv
- Append-only writes prevent data loss
- Dataclass fields define expected columns; CSV readers use `csv.DictReader`

## Developer Workflows

### Testing New Scrapers

1. Write scraper function returning `List[Dict]`
2. Test URL + parsing with breakpoint or local cache check
3. Add to ScraperService refresh flow
4. Verify delta detection finds new records

### Adding Cache for New Entity

1. Create `FooCache(BaseCsvCache[key_type, value_type])`
2. Implement three abstract methods (see FightCache for two-rows-per-key pattern)
3. Add to ScraperService.**init**() and loaders
4. Create corresponding CSV in resources/

### Running Scrapers

```bash
# From data/ directory
python -m ScraperService.refreshFightData()  # Full refresh
```

## Key Files by Purpose

- **Caching**: [cache/BaseCsvCache.py](../data/cache/BaseCsvCache.py) (template), [cache/FightCache.py](../data/cache/FightCache.py) (complex example with lists)
- **Scraping**: [scrapers/FightDataScraper.py](../data/scrapers/FightDataScraper.py) (detailed parsing), [scrapers/ScraperUtil.py](../data/scrapers/ScraperUtil.py) (shared HTTP setup)
- **Business Logic**: [ScraperService.py](../data/ScraperService.py) (orchestration)
- **API**: [FightDataResource.py](../data/FightDataResource.py) (endpoints)
- **Data Cleaning**: [data_clean/](../data_clean/) (explore_data.py, process_data.py, features.py)

## Important Notes

- Thread safety: All caches use `RLock` for concurrent access; safe to query from multiple threads
- Relative imports: Cache/scraper modules use relative imports (`.cache`, `..resources`)—check working directory
- No-overwrite guarantee: Append-only CSV design means data persists even if code crashes mid-import

## Downstream ML Pipeline (Context for Data Preparation)

The cleaned fight data feeds three ML systems:

1. **Style Modeling (NMF)**: Decomposes fighter statistics into 5 latent fighting styles (striking, muay thai, wrestling, grappling, pace). Uses non-negative factorization to ensure interpretable, non-negative style weights.

2. **Outcome Prediction (XGBoost)**: Predicts fight winners using fighter style compositions as features. Target: ≥68% precision (AUC ≥ 0.72) on time-held-out test events (test only on events after training cutoff).

3. **Explainability (SHAP)**: Generates human-interpretable explanations of predictions—identifies top 5 drivers behind each outcome (e.g., "high control % + low takedown defense → loss").

### Data Cleaning Pipeline

Raw fight stats are cleaned in [data_clean/](../data_clean/):

- **explore_data.py**: Inspect raw CSV structure and quality
- **process_data.py**: Parse "X of Y" stats → normalize per-minute → merge outcomes → train/test split
- **features.py**: Define feature sets for NMF (25 features) and XGBoost (14 features)

Output: 5 CSVs in [resources/clean_data/](../resources/clean_data/) ready for model training.

```bash
# From data_clean/
python process_data.py  # Generates train_set.csv and test_set.csv
```
