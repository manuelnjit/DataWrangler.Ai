"""DataWrangler.AI - Official Premier League Upcoming Fixtures Ingestion Engine (Task 4.5.7).

This module fetches live scheduled Premier League fixtures for upcoming matchday rounds,
normalizes team names, and stores them in `epl_quant.db` with `status = 'SCHEDULED'`.
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.matches import Match
from app.ingestion.football_data import FootballDataIngestor

logger = logging.getLogger("datawrangler.ingestion.upcoming")

PULSE_FIXTURES_URL = "https://footballapi.pulselive.com/football/fixtures"
HEADERS = {
    "Origin": "https://www.premierleague.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Mapping pulse API team names to DataWrangler.AI canonical team names
PULSE_TEAM_MAP = {
    "Wolverhampton Wanderers": "Wolves",
    "West Bromwich Albion": "West Brom",
    "Sheffield Wednesday": "Sheffield Weds",
    "Coventry City": "Coventry",
    "Hull City": "Hull",
    "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Luton Town": "Luton",
    "Norwich City": "Norwich",
    "Oldham Athletic": "Oldham",
    "Queens Park Rangers": "QPR",
    "Swindon Town": "Swindon",
    "Wigan Athletic": "Wigan",
    "Brighton and Hove Albion": "Brighton",
    "Cardiff City": "Cardiff",
    "Huddersfield Town": "Huddersfield",
    "Derby County": "Derby",
    "Tottenham Hotspur": "Tottenham",
    "Newcastle United": "Newcastle",
    "West Ham United": "West Ham",
    "Nottingham Forest": "Nottingham Forest",
    "Crystal Palace": "Crystal Palace",
    "Sheffield United": "Sheffield United",
    "Sunderland": "Sunderland",
    "Blackburn Rovers": "Blackburn",
    "Middlesbrough": "Middlesbrough",
    "Birmingham City": "Birmingham",
    "Bolton Wanderers": "Bolton",
    "Charlton Athletic": "Charlton",
    "Portsmouth": "Portsmouth",
    "Reading": "Reading",
    "Stoke City": "Stoke",
    "Swansea City": "Swansea",
    "Watford": "Watford",
}


def normalize_pulse_team_name(raw_name: str) -> str:
    """Normalizes team name using canonical map."""
    if not raw_name:
        return raw_name
    cleaned = raw_name.strip()
    return PULSE_TEAM_MAP.get(cleaned, cleaned)


class UpcomingFixturesIngestor:
    """Ingests official Premier League scheduled upcoming fixtures into database."""

    def __init__(self, db: Session):
        self.db = db

    async def fetch_and_ingest_upcoming(self, comp_season_id: int = 841, season_str: str = "2025-2026") -> int:
        """Fetches upcoming fixtures from PulseLive API and upserts into database with status='SCHEDULED'."""
        url = f"{PULSE_FIXTURES_URL}?comps=1&compSeasons={comp_season_id}&pageSize=380"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=HEADERS)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"Failed to fetch or parse upcoming fixtures: {e}. API may be blocking cloud IPs.")
                data = {}
        
        fixtures = data.get("content", [])
        ingested_count = 0

        for f in fixtures:
            # We only ingest unplayed or scheduled fixtures
            status_code = f.get("status")
            if status_code == "C":
                # Completed match - skip or leave to completed ETL
                continue

            gameweek = int(f.get("gameweek", {}).get("gameweek", 1))
            teams_data = f.get("teams", [])
            if len(teams_data) < 2:
                continue

            home_raw = teams_data[0].get("team", {}).get("name", "")
            away_raw = teams_data[1].get("team", {}).get("name", "")

            home_team = normalize_pulse_team_name(home_raw)
            away_team = normalize_pulse_team_name(away_raw)

            # Kickoff Date
            millis = f.get("kickoff", {}).get("millis")
            if millis:
                match_date = datetime.utcfromtimestamp(millis / 1000.0).date()
            else:
                match_date = date.today()

            # Upsert into matches table with status='SCHEDULED'
            existing = self.db.query(Match).filter(
                Match.season == season_str,
                Match.match_date == match_date,
                Match.home_team == home_team,
                Match.away_team == away_team,
            ).first()

            if not existing:
                match_obj = Match(
                    season=season_str,
                    matchday=gameweek,
                    match_date=match_date,
                    home_team=home_team,
                    away_team=away_team,
                    status="SCHEDULED",
                    fthg=None,
                    ftag=None,
                    ftr=None,
                    hthg=None,
                    htag=None,
                    htr=None,
                )
                self.db.add(match_obj)
                ingested_count += 1
            else:
                existing.status = "SCHEDULED"
                existing.matchday = gameweek

        self.db.commit()
        logger.info(f"Ingested {ingested_count} upcoming scheduled fixtures for season {season_str}")
        return ingested_count


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    ingestor = UpcomingFixturesIngestor(db)
    count = asyncio.run(ingestor.fetch_and_ingest_upcoming(comp_season_id=841, season_str="2025-2026"))
    print(f"Successfully ingested {count} upcoming scheduled matches!")
