"""EPL Quant - ETL Post-Processor (Medallion Gold Layer).

This script reads from the `raw_matches` table, calculates previous season finishes
and in-season ranks, and upserts the data into `enriched_matches` for instantaneous API reads.
"""

import logging
import argparse
from typing import Dict, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.database import SessionLocal
from app.models.matches import RawMatch, EnrichedMatch

logger = logging.getLogger("datawrangler.ingestion.rank_calculator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def get_previous_season_string(current_season: str) -> str:
    """Calculates the previous season string (e.g. '2023-2024' -> '2022-2023')."""
    try:
        start_yr = int(current_season.split('-')[0])
        return f"{start_yr - 1}-{start_yr}"
    except Exception:
        return None


def calculate_season_ranks(db: Session, season_str: str, league: str) -> Dict[str, int]:
    """Calculates final ranks (1 to 20/24) for a given season and league."""
    matches = db.query(RawMatch).filter(
        RawMatch.season == season_str,
        RawMatch.league == league,
        RawMatch.status == "COMPLETED",
        RawMatch.ftr.isnot(None)
    ).all()

    if not matches:
        return {}

    table_stats: Dict[str, Dict[str, int]] = {}

    for m in matches:
        h, a = m.home_team, m.away_team
        if h not in table_stats: table_stats[h] = {"pts": 0, "gf": 0, "ga": 0, "gd": 0}
        if a not in table_stats: table_stats[a] = {"pts": 0, "gf": 0, "ga": 0, "gd": 0}

        fthg, ftag = m.fthg or 0, m.ftag or 0
        table_stats[h]["gf"] += fthg
        table_stats[h]["ga"] += ftag
        table_stats[h]["gd"] += (fthg - ftag)
        table_stats[a]["gf"] += ftag
        table_stats[a]["ga"] += fthg
        table_stats[a]["gd"] += (ftag - fthg)

        if m.ftr == "H": table_stats[h]["pts"] += 3
        elif m.ftr == "A": table_stats[a]["pts"] += 3
        else:
            table_stats[h]["pts"] += 1
            table_stats[a]["pts"] += 1

    sorted_teams = sorted(
        table_stats.keys(),
        key=lambda t: (table_stats[t]["pts"], table_stats[t]["gd"], table_stats[t]["gf"]),
        reverse=True,
    )
    return {team: idx + 1 for idx, team in enumerate(sorted_teams)}


def calculate_matchday_pre_ranks(db: Session, season_str: str, matchday: int, league: str) -> Dict[str, int]:
    """Calculates standing ranks of all teams going into a target matchday."""
    if matchday <= 1:
        return {}

    prior_md = matchday - 1
    matches = db.query(RawMatch).filter(
        RawMatch.season == season_str,
        RawMatch.league == league,
        RawMatch.matchday <= prior_md,
        RawMatch.status == "COMPLETED",
        RawMatch.ftr.isnot(None)
    ).all()

    if not matches:
        return {}

    table_stats: Dict[str, Dict[str, int]] = {}

    for m in matches:
        h, a = m.home_team, m.away_team
        if h not in table_stats: table_stats[h] = {"pts": 0, "gf": 0, "ga": 0, "gd": 0}
        if a not in table_stats: table_stats[a] = {"pts": 0, "gf": 0, "ga": 0, "gd": 0}

        fthg, ftag = m.fthg or 0, m.ftag or 0
        table_stats[h]["gf"] += fthg
        table_stats[h]["ga"] += ftag
        table_stats[h]["gd"] += (fthg - ftag)
        table_stats[a]["gf"] += ftag
        table_stats[a]["ga"] += fthg
        table_stats[a]["gd"] += (ftag - fthg)

        if m.ftr == "H": table_stats[h]["pts"] += 3
        elif m.ftr == "A": table_stats[a]["pts"] += 3
        else:
            table_stats[h]["pts"] += 1
            table_stats[a]["pts"] += 1

    sorted_teams = sorted(
        table_stats.keys(),
        key=lambda t: (table_stats[t]["pts"], table_stats[t]["gd"], table_stats[t]["gf"]),
        reverse=True,
    )
    return {team: idx + 1 for idx, team in enumerate(sorted_teams)}


def determine_league_status(team: str, prev_ranks: dict, other_prev_ranks: dict, current_league: str) -> str:
    if prev_ranks.get(team):
        return "STAYED"
    if current_league == "EPL" and other_prev_ranks.get(team):
        return "PROMOTED_FROM_CHAMPIONSHIP"
    if current_league == "Championship" and other_prev_ranks.get(team):
        return "RELEGATED_FROM_EPL"
    return "UNKNOWN_OR_PROMOTED_FROM_LEAGUE_ONE"


def build_enriched_layer(audit: bool = False):
    db = SessionLocal()
    try:
        if audit:
            logger.info("AUDIT MODE: Wiping enriched_matches table...")
            db.query(EnrichedMatch).delete()
            db.commit()

        # Cache definitions
        season_cache: Dict[Tuple[str, str], Dict[str, int]] = {}
        matchday_cache: Dict[Tuple[str, str, int], Dict[str, int]] = {}

        # Fetch only matches that need to be processed
        if audit:
            pending_raw = db.query(RawMatch).order_by(RawMatch.season, RawMatch.matchday, RawMatch.match_date).all()
        else:
            # We can implement differential sync later. For now, audit mode is standard for backfilling.
            pending_raw = db.query(RawMatch).order_by(RawMatch.season, RawMatch.matchday, RawMatch.match_date).all()
            
        logger.info(f"Processing {len(pending_raw)} matches for Gold Layer...")

        for m in pending_raw:
            m_league = m.league or "EPL"
            other_league = "Championship" if m_league == "EPL" else "EPL"
            prev_s = get_previous_season_string(m.season)

            # --- 1. Previous Season Ranks ---
            prev_ranks = {}
            other_prev_ranks = {}
            if prev_s:
                if (m_league, prev_s) not in season_cache:
                    season_cache[(m_league, prev_s)] = calculate_season_ranks(db, prev_s, m_league)
                if (other_league, prev_s) not in season_cache:
                    season_cache[(other_league, prev_s)] = calculate_season_ranks(db, prev_s, other_league)
                
                prev_ranks = season_cache[(m_league, prev_s)]
                other_prev_ranks = season_cache[(other_league, prev_s)]

            h_prev = prev_ranks.get(m.home_team)
            a_prev = prev_ranks.get(m.away_team)
            
            h_status = determine_league_status(m.home_team, prev_ranks, other_prev_ranks, m_league)
            a_status = determine_league_status(m.away_team, prev_ranks, other_prev_ranks, m_league)

            # --- 2. In-Season Matchday Pre Ranks ---
            md = m.matchday or 1
            if (m_league, m.season, md) not in matchday_cache:
                matchday_cache[(m_league, m.season, md)] = calculate_matchday_pre_ranks(db, m.season, md, m_league)
            
            md_ranks = matchday_cache[(m_league, m.season, md)]
            h_pre = md_ranks.get(m.home_team)
            a_pre = md_ranks.get(m.away_team)

            # --- 3. UPSERT into EnrichedMatch ---
            existing = db.query(EnrichedMatch).filter(
                EnrichedMatch.league == m_league,
                EnrichedMatch.season == m.season,
                EnrichedMatch.home_team == m.home_team,
                EnrichedMatch.away_team == m.away_team,
                EnrichedMatch.match_date == m.match_date
            ).first()

            if not existing:
                enriched = EnrichedMatch(
                    season=m.season,
                    matchday=m.matchday,
                    match_date=m.match_date,
                    home_team=m.home_team,
                    away_team=m.away_team,
                    league=m_league,
                    status=m.status,
                    fthg=m.fthg,
                    ftag=m.ftag,
                    ftr=m.ftr,
                    hthg=m.hthg,
                    htag=m.htag,
                    htr=m.htr,
                    home_prev_rank=h_prev,
                    away_prev_rank=a_prev,
                    home_prev_league_status=h_status,
                    away_prev_league_status=a_status,
                    home_pre_rank=h_pre,
                    away_pre_rank=a_pre
                )
                db.add(enriched)
            else:
                existing.home_prev_rank = h_prev
                existing.away_prev_rank = a_prev
                existing.home_prev_league_status = h_status
                existing.away_prev_league_status = a_status
                existing.home_pre_rank = h_pre
                existing.away_pre_rank = a_pre
                existing.status = m.status
                existing.fthg = m.fthg
                existing.ftag = m.ftag
                existing.ftr = m.ftr

        db.commit()
        logger.info("Successfully built Gold Layer!")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true", help="Wipes and recalculates the entire Gold Layer")
    args = parser.parse_args()
    build_enriched_layer(audit=args.audit)
