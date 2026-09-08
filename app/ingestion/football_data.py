"""DataWrangler.AI - Football-Data.co.uk Data Ingestion Engine (33 Seasons: 1993-1994 to 2025-2026).

This module implements:
1. `FootballDataIngestor`: Async HTTP extractor fetching raw CSV text from Football-Data.co.uk.
2. Complete Historical Season Mapping (33 Premier League Seasons: 1993-1994 through 2025-2026).
3. Data Cleaning & Normalization Engine:
   - Date Formatting: Normalizes dates to strict `MM/DD/YYYY` strings (e.g., '08/11/2023').
   - Season Attribution: Adds explicit `season` column (e.g., '1999-2000', '2025-2026').
   - Matchday Calculation: Computes chronological fixture round/matchday (e.g., Matchday 1 to 38/42).
   - Team Name Standardization: Standardizes team names across 3 decades of EPL data.
4. Idempotent Database UPSERT Engine:
   - Prevents duplicate match creation regardless of how many times ingestion is executed.
"""

import csv
import io
import logging
from datetime import datetime
from typing import Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.models.matches import Match

logger = logging.getLogger("datawrangler.ingestion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class FootballDataIngestor:
    """Asynchronous ETL Extractor, Normalization Engine, and Database UPSERT Manager."""

    BASE_URL = "https://www.football-data.co.uk/mmz4281"

    # Dynamic Generator for 33 Premier League Seasons (1993-1994 through 2025-2026)
    @staticmethod
    def generate_all_seasons_map() -> Dict[str, str]:
        """Generates mapping from human season label (e.g. '1999-2000') to Football-Data 4-digit code (e.g. '9900', '2526')."""
        season_map = {}
        for start_year in range(1993, 2026):
            end_year = start_year + 1
            season_label = f"{start_year}-{end_year}"

            y1 = str(start_year)[-2:]
            y2 = str(end_year)[-2:]
            code = f"{y1}{y2}"
            season_map[season_label] = code

        return season_map

    # Standardized Premier League Team Name Mapping Dictionary
    TEAM_NAME_NORMALIZER: Dict[str, str] = {
        "Man City": "Manchester City",
        "Man United": "Manchester United",
        "Man Utd": "Manchester United",
        "Nott'm Forest": "Nottingham Forest",
        "Nottm Forest": "Nottingham Forest",
        "Sheffield Utd": "Sheffield United",
        "Newcastle Utd": "Newcastle",
        "Spurs": "Tottenham",
        "Wolverhampton": "Wolves",
        "West Bromwich": "West Brom",
        "Blackburn Rovers": "Blackburn",
        "Bolton Wanderers": "Bolton",
        "Charlton Athletic": "Charlton",
        "Coventry City": "Coventry",
        "Derby County": "Derby",
        "Ipswich Town": "Ipswich",
        "Leeds United": "Leeds",
        "Leicester City": "Leicester",
        "Middlesbrough FC": "Middlesbrough",
        "Norwich City": "Norwich",
        "Oldham Athletic": "Oldham",
        "Queens Park Rangers": "QPR",
        "Swindon Town": "Swindon",
        "Wimbledon FC": "Wimbledon",
    }

    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout = httpx.Timeout(timeout_seconds)
        self.SEASON_MAP = self.generate_all_seasons_map()

    def get_season_url(self, season_code: str, csv_code: str = "E0") -> str:
        return f"{self.BASE_URL}/{season_code}/{csv_code}.csv"

    def normalize_team_name(self, raw_name: str) -> str:
        """Normalizes team names to standardized full names."""
        clean_name = raw_name.strip()
        return self.TEAM_NAME_NORMALIZER.get(clean_name, clean_name)

    def parse_date_to_mm_dd_yyyy(self, date_str: str) -> str:
        """Parses raw date string and returns formatted MM/DD/YYYY date string."""
        clean_str = date_str.strip()
        date_obj = None

        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                date_obj = datetime.strptime(clean_str, fmt).date()
                break
            except ValueError:
                continue

        if not date_obj:
            raise ValueError(f"Unable to parse date string: '{date_str}'")

        return date_obj.strftime("%m/%d/%Y")

    async def fetch_season_csv(self, season_code: str, csv_code: str = "E0") -> Optional[str]:
        """Asynchronously fetches raw CSV text content from Football-Data.co.uk."""
        url = self.get_season_url(season_code, csv_code)
        logger.info(f"Extracting match data from Football-Data URL: {url}")

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info(f"Successfully extracted CSV for season code '{season_code}' ({len(response.text)} bytes)")
                    return response.text
                else:
                    logger.error(f"Failed to fetch CSV for season code '{season_code}'. Status: {response.status_code}")
                    return None
            except httpx.RequestError as exc:
                logger.error(f"Network error requesting {exc.request.url!r}: {exc}")
                return None

    def parse_csv_content(self, csv_text: str, season_label: str, league: str = "EPL") -> List[Dict]:
        """Parses, cleans, and normalizes raw CSV text content into structured match dictionaries."""
        cleaned_records: List[Dict] = []
        reader = csv.DictReader(io.StringIO(csv_text))

        for row in reader:
            if not row.get("Date") or not row.get("HomeTeam") or not row.get("AwayTeam"):
                continue

            try:
                formatted_date = self.parse_date_to_mm_dd_yyyy(row["Date"])
                home_team = self.normalize_team_name(row["HomeTeam"])
                away_team = self.normalize_team_name(row["AwayTeam"])

                fthg = int(row["FTHG"]) if row.get("FTHG") and row["FTHG"].isdigit() else 0
                ftag = int(row["FTAG"]) if row.get("FTAG") and row["FTAG"].isdigit() else 0
                ftr = row.get("FTR", "D").strip().upper()

                hthg = int(row["HTHG"]) if row.get("HTHG") and row["HTHG"].isdigit() else 0
                htag = int(row["HTAG"]) if row.get("HTAG") and row["HTAG"].isdigit() else 0
                htr = row.get("HTR", "D").strip().upper() if row.get("HTR") else ftr

                record = {
                    "league": league,
                    "season": season_label,
                    "match_date_str": formatted_date,
                    "match_date": datetime.strptime(formatted_date, "%m/%d/%Y").date(),
                    "home_team": home_team,
                    "away_team": away_team,
                    "fthg": fthg,
                    "ftag": ftag,
                    "ftr": ftr,
                    "hthg": hthg,
                    "htag": htag,
                    "htr": htr,
                }
                cleaned_records.append(record)

            except Exception as e:
                logger.warning(f"Skipping malformed CSV row ({row.get('HomeTeam')} vs {row.get('AwayTeam')}): {e}")

        # Sort cleaned records chronologically by match_date to assign matchdays
        cleaned_records.sort(key=lambda r: r["match_date"])
        team_counts: Dict[str, int] = {}
        for r in cleaned_records:
            h = r["home_team"]
            a = r["away_team"]
            team_counts[h] = team_counts.get(h, 0) + 1
            team_counts[a] = team_counts.get(a, 0) + 1
            r["matchday"] = max(team_counts[h], team_counts[a])

        logger.info(f"Parsed & normalized {len(cleaned_records)} fixtures for season '{season_label}'")
        return cleaned_records

    def save_matches_to_db(self, db: Session, cleaned_records: List[Dict]) -> Dict[str, int]:
        """Saves cleaned match records into SQLite using an idempotent UPSERT pattern."""
        inserted_count = 0
        updated_count = 0

        for rec in cleaned_records:
            existing_match = db.query(Match).filter(
                Match.league == rec["league"],
                Match.season == rec["season"],
                Match.match_date == rec["match_date"],
                Match.home_team == rec["home_team"],
                Match.away_team == rec["away_team"],
            ).first()

            if existing_match:
                existing_match.matchday = rec["matchday"]
                existing_match.fthg = rec["fthg"]
                existing_match.ftag = rec["ftag"]
                existing_match.ftr = rec["ftr"]
                existing_match.hthg = rec["hthg"]
                existing_match.htag = rec["htag"]
                existing_match.htr = rec["htr"]
                updated_count += 1
            else:
                new_match = Match(
                    league=rec["league"],
                    season=rec["season"],
                    matchday=rec["matchday"],
                    match_date=rec["match_date"],
                    home_team=rec["home_team"],
                    away_team=rec["away_team"],
                    fthg=rec["fthg"],
                    ftag=rec["ftag"],
                    ftr=rec["ftr"],
                    hthg=rec["hthg"],
                    htag=rec["htag"],
                    htr=rec["htr"],
                )
                db.add(new_match)
                inserted_count += 1

        db.commit()
        stats = {
            "processed": len(cleaned_records),
            "inserted": inserted_count,
            "updated": updated_count,
        }
        return stats

    async def ingest_season(self, db: Session, season_label: str, csv_code: str = "E0", league: str = "EPL") -> Dict[str, int]:
        """Extracts, cleans, and saves a season's match data into SQLite."""
        code = self.SEASON_MAP.get(season_label)
        if not code:
            logger.error(f"Unknown season label: '{season_label}'")
            return {"processed": 0, "inserted": 0, "updated": 0}

        csv_text = await self.fetch_season_csv(code, csv_code)
        if not csv_text:
            return {"processed": 0, "inserted": 0, "updated": 0}

        cleaned_records = self.parse_csv_content(csv_text, season_label, league)
        return self.save_matches_to_db(db, cleaned_records)

    async def ingest_all_historical_seasons(self, db: Session, csv_code: str = "E0", league: str = "EPL") -> Dict[str, int]:
        """Ingests all 33 historical seasons (1993-1994 through 2025-2026) into SQLite."""
        all_seasons = sorted(list(self.SEASON_MAP.keys()), reverse=True)
        logger.info(f"Starting complete historical ingestion of {len(all_seasons)} {league} seasons...")

        total_stats = {"processed": 0, "inserted": 0, "updated": 0}
        for s in all_seasons:
            stats = await self.ingest_season(db, s, csv_code, league)
            total_stats["processed"] += stats["processed"]
            total_stats["inserted"] += stats["inserted"]
            total_stats["updated"] += stats["updated"]

        logger.info(
            f"Complete 33-Season Historical Ingestion Finished: Processed={total_stats['processed']}, "
            f"Inserted={total_stats['inserted']}, Updated={total_stats['updated']}"
        )
        return total_stats
