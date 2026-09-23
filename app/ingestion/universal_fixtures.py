"""DataWrangler.AI - Unified Universal Fixtures Ingestion Engine.

This module replaces league-specific scrapers. It reads `app/config/leagues.json`,
loops through configured leagues, fetches full season matches from football-data.org,
and automatically throttles based on HTTP headers to respect API limits.
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime, date
from typing import Optional, Dict
import httpx
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.matches import RawMatch

logger = logging.getLogger("datawrangler.ingestion.universal")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

API_KEY = os.environ.get("FOOTBALL_DATA_ORG_KEY")
if not API_KEY:
    logger.error("FOOTBALL_DATA_ORG_KEY environment variable is missing. The API requires a key.")
    sys.exit(1)

BASE_URL = "https://api.football-data.org/v4"
HEADERS = {
    "X-Auth-Token": API_KEY
}

# Unified mapping for football-data.org team names to DataWrangler.AI canonical team names
TEAM_MAP = {
    "Queens Park Rangers FC": "QPR",
    "West Bromwich Albion FC": "West Brom",
    "Preston North End FC": "Preston",
    "Coventry City FC": "Coventry",
    "Sheffield Wednesday FC": "Sheffield Weds",
    "Luton Town FC": "Luton",
    "Norwich City FC": "Norwich",
    "Cardiff City FC": "Cardiff",
    "Derby County FC": "Derby",
    "Sheffield United FC": "Sheffield United",
    "Sunderland AFC": "Sunderland",
    "Blackburn Rovers FC": "Blackburn",
    "Middlesbrough FC": "Middlesbrough",
    "Birmingham City FC": "Birmingham",
    "Swansea City AFC": "Swansea",
    "Watford FC": "Watford",
    "Leeds United FC": "Leeds",
    "Hull City AFC": "Hull",
    "Stoke City FC": "Stoke",
    "Bristol City FC": "Bristol City",
    "Burnley FC": "Burnley",
    "Millwall FC": "Millwall",
    "Plymouth Argyle FC": "Plymouth",
    "Portsmouth FC": "Portsmouth",
    "Oxford United FC": "Oxford",
    "Sheffield Wednesday": "Sheffield Weds",
    "Bolton Wanderers FC": "Bolton",
    "Charlton Athletic FC": "Charlton",
    
    # Premier League
    "Manchester City FC": "Manchester City",
    "Manchester United FC": "Manchester United",
    "Nottingham Forest FC": "Nottingham Forest",
    "Newcastle United FC": "Newcastle",
    "Tottenham Hotspur FC": "Tottenham",
    "Wolverhampton Wanderers FC": "Wolves",
    "Leicester City FC": "Leicester",
    "Arsenal FC": "Arsenal",
    "Aston Villa FC": "Aston Villa",
    "Brentford FC": "Brentford",
    "Brighton & Hove Albion FC": "Brighton",
    "Chelsea FC": "Chelsea",
    "Crystal Palace FC": "Crystal Palace",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Liverpool FC": "Liverpool",
    "Southampton FC": "Southampton",
    "West Ham United FC": "West Ham",
    "AFC Bournemouth": "Bournemouth",
    "Ipswich Town FC": "Ipswich",
}

def normalize_team_name(raw_name: str) -> str:
    """Normalizes team name using canonical map."""
    if not raw_name:
        return raw_name
    cleaned = raw_name.strip()
    return TEAM_MAP.get(cleaned, cleaned.replace(" FC", "").replace(" AFC", "").replace(" City", ""))


class UniversalFixturesIngestor:
    """Ingests full season fixtures for all configured leagues into the database."""

    def __init__(self, db: Session):
        self.db = db
        # Load league config
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "leagues.json")
        try:
            with open(config_path, "r") as f:
                self.leagues_config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load leagues.json: {e}")
            self.leagues_config = {}

    def get_current_season_string(self) -> str:
        now = datetime.now()
        current_year = now.year
        max_start_year = current_year if now.month >= 7 else current_year - 1
        return f"{max_start_year}-{max_start_year + 1}"

    async def fetch_and_ingest(self, season_str: Optional[str] = None):
        """Iterates through configured leagues and ingests fixtures."""
        if not season_str:
            season_str = self.get_current_season_string()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for league_name, config in self.leagues_config.items():
                provider_code = config.get("provider_code")
                if not provider_code:
                    logger.warning(f"Skipping {league_name}: No provider_code configured.")
                    continue
                
                logger.info(f"Fetching fixtures for {league_name} ({provider_code})...")
                url = f"{BASE_URL}/competitions/{provider_code}/matches"

                try:
                    resp = await client.get(url, headers=HEADERS)
                    resp.raise_for_status()

                    # Handle Throttle Headers
                    avail = resp.headers.get("x-requests-available-minute")
                    reset = resp.headers.get("X-RequestCounter-Reset")
                    if avail is not None and int(avail) <= 1:
                        sleep_time = int(reset) if reset else 60
                        logger.warning(f"API Rate limit nearing. Sleeping for {sleep_time} seconds...")
                        await asyncio.sleep(sleep_time)

                    data = resp.json()
                    await self._process_matches(data.get("matches", []), league_name, season_str)

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        reset = e.response.headers.get("X-RequestCounter-Reset", 60)
                        logger.error(f"Rate limited! Sleeping for {reset} seconds then retrying...")
                        await asyncio.sleep(int(reset))
                        # Retry logic for production would go here, omitting for simplicity of this script
                    else:
                        logger.error(f"HTTP Error fetching {league_name}: {e.response.text}")
                except Exception as e:
                    logger.error(f"Error processing {league_name}: {e}")

    async def _process_matches(self, matches: list, league_name: str, season_str: str):
        ingested_count = 0
        updated_count = 0

        for m in matches:
            matchday = m.get("matchday")
            if not matchday:
                continue

            home_raw = m.get("homeTeam", {}).get("name", "")
            away_raw = m.get("awayTeam", {}).get("name", "")
            if not home_raw or not away_raw:
                continue

            home_team = normalize_team_name(home_raw)
            away_team = normalize_team_name(away_raw)

            utc_date_str = m.get("utcDate")
            if utc_date_str:
                try:
                    match_date = datetime.strptime(utc_date_str, "%Y-%m-%dT%H:%M:%SZ").date()
                except ValueError:
                    match_date = date.today()
            else:
                match_date = date.today()

            # Status mapping
            raw_status = m.get("status", "SCHEDULED")
            status = "COMPLETED" if raw_status in ["FINISHED", "AWARDED"] else "SCHEDULED"

            fthg = None
            ftag = None
            if status == "COMPLETED":
                score = m.get("score", {}).get("fullTime", {})
                fthg = score.get("home")
                ftag = score.get("away")

            # Upsert into matches table
            existing = self.db.query(RawMatch).filter(
                RawMatch.league == league_name,
                RawMatch.season == season_str,
                RawMatch.home_team == home_team,
                RawMatch.away_team == away_team
            ).first()

            if not existing:
                new_match = RawMatch(
                    league=league_name,
                    season=season_str,
                    match_date=match_date,
                    matchday=matchday,
                    home_team=home_team,
                    away_team=away_team,
                    fthg=fthg,
                    ftag=ftag,
                    status=status,
                )
                self.db.add(new_match)
                ingested_count += 1
            else:
                existing.match_date = match_date
                existing.matchday = matchday
                existing.status = status
                # Update scores only if completed
                if status == "COMPLETED":
                    existing.fthg = fthg
                    existing.ftag = ftag
                updated_count += 1

        self.db.commit()
        logger.info(f"[{league_name}] Inserted {ingested_count}, Updated {updated_count} matches for season {season_str}.")

async def main():
    db = SessionLocal()
    try:
        ingestor = UniversalFixturesIngestor(db)
        await ingestor.fetch_and_ingest()
    except Exception as e:
        logger.error(f"Fatal error during universal ingestion: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
