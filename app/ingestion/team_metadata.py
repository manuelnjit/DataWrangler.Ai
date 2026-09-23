import asyncio
import logging
import httpx
import os
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.matches import Match
from app.models.teams import Team

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CRESTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "images", "crests")

ALIAS_MAP = {
    "Peterboro": "Peterborough United",
    "Sheff Wed": "Sheffield Wednesday",
    "Sheffield Weds": "Sheffield Wednesday",
    "Sheff Utd": "Sheffield United",
    "Wimbledon": "AFC Wimbledon",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Nott'm Forest": "Nottingham Forest",
    "Newcastle": "Newcastle United",
    "Tottenham": "Tottenham Hotspur",
    "Leicester": "Leicester City",
    "Leeds": "Leeds United",
    "Luton": "Luton Town",
    "Norwich": "Norwich City",
    "Cardiff": "Cardiff City",
    "Swansea": "Swansea City",
    "Stoke": "Stoke City",
    "Hull": "Hull City",
    "QPR": "Queens Park Rangers",
    "West Brom": "West Bromwich Albion",
    "West Ham": "West Ham United",
    "Bolton": "Bolton Wanderers",
    "Blackburn": "Blackburn Rovers",
    "Wigan": "Wigan Athletic",
    "Charlton": "Charlton Athletic",
    "Birmingham": "Birmingham City",
    "Derby": "Derby County",
    "Portsmouth": "Portsmouth",
    "Coventry": "Coventry City",
    "Ipswich": "Ipswich Town",
    "Bradford": "Bradford City",
    "Colchester": "Colchester United",
    "Crewe": "Crewe Alexandra",
    "Doncaster": "Doncaster Rovers",
    "Grimsby": "Grimsby Town",
    "Huddersfield": "Huddersfield Town",
    "Lincoln": "Lincoln City",
    "Oldham": "Oldham Athletic",
    "Oxford": "Oxford United",
    "Plymouth": "Plymouth Argyle",
    "Preston": "Preston North End",
    "Rotherham": "Rotherham United",
    "Scunthorpe": "Scunthorpe United",
    "Southend": "Southend United",
    "Stockport": "Stockport County",
    "Swindon": "Swindon Town",
    "Tranmere": "Tranmere Rovers",
    "Wolves": "Wolverhampton Wanderers",
    "Wycombe": "Wycombe Wanderers",
    "Yeovil": "Yeovil Town",
    "Brighton": "Brighton & Hove Albion"
}

# Fallbacks for extreme historical teams that aren't easily found in the standard API
STATIC_FALLBACKS = {
    "Bury": "https://a.espncdn.com/i/teamlogos/soccer/500/292.png",
    "Oldham Athletic": "https://r2.thesportsdb.com/images/media/team/badge/36hve81625514026.png"
}

class TeamMetadataIngestor:
    def __init__(self, db: Session):
        self.db = db
        os.makedirs(CRESTS_DIR, exist_ok=True)
        self.espn_cache = {}

    async def prefetch_espn_teams(self, client: httpx.AsyncClient):
        logger.info("Pre-fetching ESPN API directories...")
        # Fetch tiers 1-5 to guarantee we get every PL, Championship, L1, L2, and National League team
        for l in ["eng.1", "eng.2", "eng.3", "eng.4", "eng.5"]:
            try:
                res = await client.get(f"http://site.api.espn.com/apis/site/v2/sports/soccer/{l}/teams")
                res.raise_for_status()
                data = res.json()
                if "sports" not in data:
                    continue
                teams = data.get("sports", [])[0].get("leagues", [])[0].get("teams", [])
                for t in teams:
                    team = t["team"]
                    name = team["name"]
                    logos = team.get("logos", [])
                    if logos:
                        self.espn_cache[name] = logos[0]["href"]
            except Exception as e:
                logger.error(f"Failed fetching {l}: {e}")

    async def download_and_save_logo(self, client: httpx.AsyncClient, team_name: str, logo_url: str) -> str:
        safe_name = team_name.lower().replace(" ", "_").replace("'", "").replace("&", "and")
        local_filename = f"{safe_name}.png"
        local_path = os.path.join(CRESTS_DIR, local_filename)
        
        if os.path.exists(local_path):
            return f"/static/images/crests/{local_filename}"

        try:
            resp = await client.get(logo_url)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)
            return f"/static/images/crests/{local_filename}"
        except Exception as e:
            logger.error(f"Failed to download image for {team_name}: {e}")
            return None

    async def process_teams(self):
        home_teams = [t[0] for t in self.db.query(Match.home_team).distinct().all() if t[0]]
        away_teams = [t[0] for t in self.db.query(Match.away_team).distinct().all() if t[0]]
        all_teams = sorted(list(set(home_teams + away_teams)))

        logger.info(f"Discovered {len(all_teams)} unique teams across EPL and Championship.")

        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
            await self.prefetch_espn_teams(client)

            for team_name in all_teams:
                existing = self.db.query(Team).filter(Team.name == team_name).first()
                if existing and existing.logo_path:
                    continue

                logger.info(f"Processing missing metadata for: {team_name}")
                search_query = ALIAS_MAP.get(team_name, team_name)
                
                logo_url = self.espn_cache.get(search_query) or STATIC_FALLBACKS.get(search_query)
                
                local_path = None
                if logo_url:
                    local_path = await self.download_and_save_logo(client, team_name, logo_url)
                else:
                    logger.warning(f"No official logo found for {team_name}. Defaulting to generic.")

                if existing:
                    existing.logo_path = local_path
                else:
                    new_team = Team(name=team_name, logo_path=local_path)
                    self.db.add(new_team)
                
                self.db.commit()

        logger.info("Team metadata ingestion complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db_session = SessionLocal()
    try:
        ingestor = TeamMetadataIngestor(db_session)
        asyncio.run(ingestor.process_teams())
    finally:
        db_session.close()
