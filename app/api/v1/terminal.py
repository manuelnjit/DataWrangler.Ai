"""DataWrangler.AI - Live Database Terminal APIs (Task 4.5.7).

This router exposes endpoints for authenticated users to:
1. Fetch distinct Premier League team names stored in `epl_quant.db` (`GET /teams`).
2. Fetch distinct Premier League seasons stored in `epl_quant.db` (`GET /seasons`).
3. Query matchday-by-matchday Premier League standings with previous season finish & PROMOTED tagging (`GET /standings`).
4. Fetch scheduled upcoming Premier League fixtures with 1-click model scenario params (`GET /upcoming`).
5. Query raw SQL match data records with matchday, venue perspective, season range filtering, prior season rank filters, in-season pre-match rank filters, & live HT/FT empirical statistics (`GET /matches`).
6. Calculate empirical scenario probabilities dynamically against real database records (`GET /calculate`).
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.db.database import get_db
from app.models.matches import EnrichedMatch as Match
from app.models.teams import Team
from app.models.users import User
from app.api.v1.auth import get_current_user_from_request

logger = logging.getLogger("datawrangler.terminal")

router = APIRouter(prefix="/terminal", tags=["Terminal Data & Modeling"])

# In-Memory Cache for Final Season Standings to provide sub-millisecond prior season rank lookups
_SEASON_STANDINGS_CACHE: Dict[Tuple[str, str], Dict[str, int]] = {}
_MATCHDAY_STANDINGS_CACHE: Dict[Tuple[str, str], Dict[int, Dict[str, int]]] = {}

# In-Memory Cache for Final Season Standings to provide sub-millisecond prior season rank lookups


def get_season_final_ranks(db: Session, season_str: str, league: str) -> Dict[str, int]:
    """Calculates final ranks (1 to 20/24) for a given season and league. Returns dict mapping team_name -> rank integer."""
    cache_key = (league, season_str)
    if cache_key in _SEASON_STANDINGS_CACHE:
        return _SEASON_STANDINGS_CACHE[cache_key]

    matches = db.query(Match).filter(
        Match.season == season_str,
        Match.league == league,
        Match.status == "COMPLETED",
        Match.ftr.isnot(None)
    ).all()

    if not matches:
        return {}

    table_stats: Dict[str, Dict[str, int]] = {}

    for m in matches:
        h = m.home_team
        a = m.away_team

        if h not in table_stats:
            table_stats[h] = {"pts": 0, "gf": 0, "ga": 0, "gd": 0}
        if a not in table_stats:
            table_stats[a] = {"pts": 0, "gf": 0, "ga": 0, "gd": 0}

        fthg = m.fthg or 0
        ftag = m.ftag or 0

        table_stats[h]["gf"] += fthg
        table_stats[h]["ga"] += ftag
        table_stats[h]["gd"] += (fthg - ftag)

        table_stats[a]["gf"] += ftag
        table_stats[a]["ga"] += fthg
        table_stats[a]["gd"] += (ftag - fthg)

        if m.ftr == "H":
            table_stats[h]["pts"] += 3
        elif m.ftr == "A":
            table_stats[a]["pts"] += 3
        else:
            table_stats[h]["pts"] += 1
            table_stats[a]["pts"] += 1

    # Sort teams by Points -> Goal Difference -> Goals For
    sorted_teams = sorted(
        table_stats.keys(),
        key=lambda t: (table_stats[t]["pts"], table_stats[t]["gd"], table_stats[t]["gf"]),
        reverse=True,
    )

    rank_map = {team_name: idx + 1 for idx, team_name in enumerate(sorted_teams)}
    _SEASON_STANDINGS_CACHE[cache_key] = rank_map
    return rank_map


def get_matchday_pre_ranks(db: Session, season_str: str, target_matchday: int, league: str) -> Dict[str, int]:
    """Calculates standing ranks of all teams in a league going into target_matchday (using matches up to target_matchday - 1)."""
    if target_matchday <= 1:
        return {}

    prior_md = target_matchday - 1
    cache_key = (league, season_str)
    if cache_key in _MATCHDAY_STANDINGS_CACHE and prior_md in _MATCHDAY_STANDINGS_CACHE[cache_key]:
        return _MATCHDAY_STANDINGS_CACHE[cache_key][prior_md]

    matches = db.query(Match).filter(
        Match.season == season_str,
        Match.league == league,
        Match.matchday <= prior_md,
        Match.status == "COMPLETED",
        Match.ftr.isnot(None)
    ).all()

    table_stats: Dict[str, Dict[str, int]] = {}
    for m in matches:
        h = m.home_team
        a = m.away_team

        if h not in table_stats:
            table_stats[h] = {"pts": 0, "gf": 0, "ga": 0, "gd": 0}
        if a not in table_stats:
            table_stats[a] = {"pts": 0, "gf": 0, "ga": 0, "gd": 0}

        fthg = m.fthg or 0
        ftag = m.ftag or 0

        table_stats[h]["gf"] += fthg
        table_stats[h]["ga"] += ftag
        table_stats[h]["gd"] += (fthg - ftag)

        table_stats[a]["gf"] += ftag
        table_stats[a]["ga"] += fthg
        table_stats[a]["gd"] += (ftag - fthg)

        if m.ftr == "H":
            table_stats[h]["pts"] += 3
        elif m.ftr == "A":
            table_stats[a]["pts"] += 3
        else:
            table_stats[h]["pts"] += 1
            table_stats[a]["pts"] += 1

    sorted_teams = sorted(
        table_stats.keys(),
        key=lambda t: (table_stats[t]["pts"], table_stats[t]["gd"], table_stats[t]["gf"]),
        reverse=True,
    )

    rank_map = {team_name: idx + 1 for idx, team_name in enumerate(sorted_teams)}

    if cache_key not in _MATCHDAY_STANDINGS_CACHE:
        _MATCHDAY_STANDINGS_CACHE[cache_key] = {}
    _MATCHDAY_STANDINGS_CACHE[cache_key][prior_md] = rank_map

    return rank_map


def get_previous_season_string(current_season: str) -> Optional[str]:
    """Given '2023-2024', returns '2022-2023'. Returns None for '1993-1994'."""
    try:
        start_year = int(current_season.split("-")[0])
        if start_year <= 1993:
            return None
        prev_start = start_year - 1
        prev_end = start_year
        return f"{prev_start}-{prev_end}"
    except Exception:
        return None


def match_rank_filter(rank_val: Optional[int], is_promoted: bool, filter_str: Optional[str]) -> bool:
    """Matches a numeric rank or promoted flag against a filter string ('ALL', 'PROMOTED', 'TOP4', 'TOP6', 'MIDTABLE', 'BOTTOM5', 'BOTTOMHALF', or integer '1'-'20')."""
    if not filter_str or filter_str == "ALL":
        return True

    if filter_str == "PROMOTED":
        return is_promoted

    if is_promoted:
        return False

    if not rank_val:
        return False

    if filter_str == "TOP4":
        return 1 <= rank_val <= 4
    if filter_str == "TOP6":
        return 1 <= rank_val <= 6
    if filter_str == "MIDTABLE":
        return 5 <= rank_val <= 12
    if filter_str == "BOTTOMHALF":
        return 13 <= rank_val <= 17
    if filter_str == "BOTTOM5":
        return 16 <= rank_val <= 20

    if filter_str.isdigit():
        return rank_val == int(filter_str)

    return True


@router.get("/teams")
def get_available_teams(
    league: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_request),
):
    """Returns a sorted list of unique team objects (name and logo_path) stored in the database.
    
    Design Decision (Task 4.5): 
    Previously, this endpoint returned a simple List[str] of team names by running a DISTINCT query
    against the `matches` table. Now, it queries the new `teams` table to retrieve both the
    normalized team name and the local filepath to their official crest logo. This allows the frontend
    dropdowns and UI components to natively render club badges.
    
    Returns:
        List[Dict[str, str]]: JSON array of objects with keys 'name' and 'logo'.
    """
    query_home = db.query(Match.home_team).distinct()
    query_away = db.query(Match.away_team).distinct()
    
    if league and league != "ALL":
        query_home = query_home.filter(Match.league == league)
        query_away = query_away.filter(Match.league == league)
        
    home_teams = [t[0] for t in query_home.all() if t[0]]
    away_teams = [t[0] for t in query_away.all() if t[0]]
    teams_set = set(home_teams + away_teams)
    
    sorted_team_names = sorted(list(teams_set))
    
    # Batch query the Team metadata table to fetch the logo paths
    team_metadata = db.query(Team).filter(Team.name.in_(sorted_team_names)).all()
    logo_map = {t.name: t.logo_path for t in team_metadata}
    
    response_payload = []
    for team_name in sorted_team_names:
        response_payload.append({
            "name": team_name,
            "logo": logo_map.get(team_name) or "/static/images/crests/generic.png"
        })

    return response_payload


@router.get("/seasons", response_model=List[str])
def get_available_seasons(
    league: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_request),
):
    """Returns a sorted list of unique Premier League seasons stored in the database."""
    query = db.query(Match.season).distinct()
    if league and league != "ALL":
        query = query.filter(Match.league == league)
    seasons = query.all()
    season_list = [s for (s,) in seasons if s]
    return sorted(season_list, reverse=True)

@router.get("/leagues", response_model=List[str])
def get_available_leagues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_request),
):
    """Returns a sorted list of unique league names stored in the database."""
    leagues = db.query(Match.league).distinct().all()
    league_list = [l for (l,) in leagues if l]
    return sorted(league_list)



@router.get("/standings")
def get_league_standings(
    league: Optional[str] = None,
    season: Optional[str] = None,
    matchday: Optional[int] = None,
    table_type: Optional[str] = "overall",  # 'overall', 'home', 'away'
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_request),
):
    """Calculates matchday-by-matchday Premier League standings for any season, with prior season rank & PROMOTED tagging."""
    if not season:
        latest = db.query(Match.season).order_by(Match.season.desc()).first()
        season = latest[0] if latest else "2026-2027"

    query = db.query(Match).filter(
        Match.season == season,
        Match.status == "COMPLETED",
        Match.ftr.isnot(None)
    )
    if league and league != "ALL":
        query = query.filter(Match.league == league)
    if matchday is not None and matchday > 0:
        query = query.filter(Match.matchday <= matchday)

    matches = query.order_by(Match.match_date).all()

    # Get Previous Season Ranks
    league_to_use = league if league and league != "ALL" else "EPL"
    prev_season_str = get_previous_season_string(season)
    prev_rank_map = get_season_final_ranks(db, prev_season_str, league_to_use) if prev_season_str else {}
    
    other_league = "Championship" if league_to_use == "EPL" else "EPL"
    other_prev_rank_map = get_season_final_ranks(db, prev_season_str, other_league) if prev_season_str else {}

    table_data: Dict[str, Dict] = {}

    for m in matches:
        h = m.home_team
        a = m.away_team
        fthg = m.fthg or 0
        ftag = m.ftag or 0

        for team_name in (h, a):
            if team_name not in table_data:
                # Prior Season Rank Label
                if not prev_season_str:
                    prev_label = "N/A"
                elif team_name in prev_rank_map:
                    prev_label = f"#{prev_rank_map[team_name]}"
                else:
                    if league_to_use == "EPL":
                        prev_label = "Promoted"
                    else:
                        prev_label = "Relegated" if team_name in other_prev_rank_map else "Promoted"

                table_data[team_name] = {
                    "team": team_name,
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "gf": 0,
                    "ga": 0,
                    "gd": 0,
                    "points": 0,
                    "prev_rank": prev_label,
                    "is_promoted": (prev_label == "PROMOTED"),
                }

        # Overall vs Home vs Away Table Calculation
        if table_type in ("overall", "home"):
            t_h = table_data[h]
            t_h["played"] += 1
            t_h["gf"] += fthg
            t_h["ga"] += ftag
            t_h["gd"] += (fthg - ftag)
            if m.ftr == "H":
                t_h["won"] += 1
                t_h["points"] += 3
            elif m.ftr == "D":
                t_h["drawn"] += 1
                t_h["points"] += 1
            else:
                t_h["lost"] += 1

        if table_type in ("overall", "away"):
            t_a = table_data[a]
            t_a["played"] += 1
            t_a["gf"] += ftag
            t_a["ga"] += fthg
            t_a["gd"] += (ftag - fthg)
            if m.ftr == "A":
                t_a["won"] += 1
                t_a["points"] += 3
            elif m.ftr == "D":
                t_a["drawn"] += 1
                t_a["points"] += 1
            else:
                t_a["lost"] += 1

    # Sort table by Points -> Goal Difference -> Goals For
    sorted_standings = sorted(
        table_data.values(),
        key=lambda r: (r["points"], r["gd"], r["gf"]),
        reverse=True,
    )

    # Batch query Team metadata to inject logos
    team_names = [r["team"] for r in sorted_standings]
    teams_meta = db.query(Team).filter(Team.name.in_(team_names)).all()
    logo_map = {t.name: t.logo_path for t in teams_meta}

    for idx, row in enumerate(sorted_standings):
        row["pos"] = idx + 1
        row["logo"] = logo_map.get(row["team"]) or "/static/images/crests/generic.png"

    return {
        "season": season,
        "matchday_filter": matchday or "Full Season",
        "table_type": table_type,
        "total_teams": len(sorted_standings),
        "standings": sorted_standings,
    }


@router.get("/upcoming")
def get_upcoming_scheduled_fixtures(
    league: Optional[str] = None,
    season: Optional[str] = None,
    matchday: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_request),
):
    """Fetches upcoming (or historical) fixtures for a given matchday."""
    if not season:
        latest = db.query(Match.season).order_by(Match.season.desc()).first()
        season = latest[0] if latest else "2026-2027"

    query = db.query(Match).filter(Match.season == season)
    
    if league and league != "ALL":
        query = query.filter(Match.league == league)

    if matchday is not None and matchday > 0:
        query = query.filter(Match.matchday == matchday)
    else:
        # Default to the matchday of the NEXT chronological scheduled match
        today = datetime.now().date()
        next_scheduled = query.filter(Match.status == "SCHEDULED", Match.match_date >= today).order_by(Match.match_date).first()
        
        if next_scheduled and next_scheduled.matchday:
            target_md = next_scheduled.matchday
            query = query.filter(Match.matchday == target_md)
        else:
            # If no future scheduled matches (e.g. season is over or no future matches ingested),
            # fallback to the highest COMPLETED matchday
            last_completed = query.filter(Match.status == "COMPLETED").order_by(Match.matchday.desc()).first()
            if last_completed and last_completed.matchday:
                target_md = last_completed.matchday
                query = query.filter(Match.matchday == target_md)
            else:
                # Absolute fallback if db is totally empty for this league
                query = query.filter(Match.matchday == 1)

    upcoming_matches = query.order_by(Match.matchday, Match.match_date, Match.home_team).all()

    # Pre-fetch logos
    all_teams_meta = db.query(Team).all()
    logo_map = {t.name: t.logo_path for t in all_teams_meta}

    results = []
    for m in upcoming_matches:
        results.append({
            "id": m.id,
            "season": m.season,
            "matchday": m.matchday,
            "match_date": m.match_date.strftime("%m/%d/%Y") if m.match_date else None,
            "home_team": m.home_team,
            "home_logo": logo_map.get(m.home_team) or "/static/images/crests/generic.png",
            "away_team": m.away_team,
            "away_logo": logo_map.get(m.away_team) or "/static/images/crests/generic.png",
            "status": m.status,
            "fthg": m.fthg,
            "ftag": m.ftag
        })

    return {
        "season": season,
        "total_upcoming": len(results),
        "matches": results,
    }


@router.get("/matchday-history")
def get_matchday_history(
    team_a: str,
    team_b: str,
    exact: bool = False,
    limit: str = "5",
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_request)
):
    """
    Retrieves historical head-to-head matches between two teams.
    If exact=True, team_a must be home and team_b must be away.
    If exact=False, returns all matches between the two regardless of venue.
    limit can be an integer string or 'all'.
    """
    from sqlalchemy import or_, and_, desc
    
    query = db.query(Match).filter(Match.status == "COMPLETED")

    if exact:
        query = query.filter(
            and_(Match.home_team == team_a, Match.away_team == team_b)
        )
    else:
        query = query.filter(
            or_(
                and_(Match.home_team == team_a, Match.away_team == team_b),
                and_(Match.home_team == team_b, Match.away_team == team_a)
            )
        )
    
    # Sort by most recent match date
    query = query.order_by(desc(Match.match_date))
    
    if limit.lower() != "all":
        try:
            lim_val = int(limit)
            query = query.limit(lim_val)
        except ValueError:
            pass

    matches = query.all()

    # Pre-fetch logos
    all_teams_meta = db.query(Team).all()
    logo_map = {t.name: t.logo_path for t in all_teams_meta}

    results = []
    for m in matches:
        # Determine exact scores safely (just in case they are null)
        h_score = m.fthg if m.fthg is not None else "N/A"
        a_score = m.ftag if m.ftag is not None else "N/A"
        ht_h_score = m.hthg if m.hthg is not None else "N/A"
        ht_a_score = m.htag if m.htag is not None else "N/A"
        
        results.append({
            "season": m.season,
            "match_date": m.match_date,
            "home_team": m.home_team,
            "home_logo": logo_map.get(m.home_team) or "/static/images/crests/generic.png",
            "away_team": m.away_team,
            "away_logo": logo_map.get(m.away_team) or "/static/images/crests/generic.png",
            "ht_score": f"{ht_h_score} - {ht_a_score}",
            "ft_score": f"{h_score} - {a_score}"
        })
    
    return {"matches": results}



@router.get("/matches")
def get_raw_matches_table(
    league: Optional[str] = None,
    season: Optional[str] = None,
    start_season: Optional[str] = None,
    end_season: Optional[str] = None,
    matchday: Optional[int] = None,
    team: Optional[str] = None,
    team1: Optional[str] = None,
    team2: Optional[str] = None,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    venue_role: Optional[str] = "all",  # 'all', 'home', 'away'
    home_prev_filter: Optional[str] = None,  # 'ALL', 'TOP4', 'PROMOTED', '1'-'17'
    away_prev_filter: Optional[str] = None,
    home_pre_filter: Optional[str] = None,   # 'ALL', 'TOP4', '1'-'20'
    away_pre_filter: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_request),
):
    """Returns raw SQL match records with server-side Matchday, Head-to-Head, Season Range, Standing Rank Filters, & live HT/FT empirical statistics."""
    query = db.query(Match).filter(Match.status == "COMPLETED")
    
    if league and league != "ALL":
        query = query.filter(Match.league == league)

    # Single Season vs Season Range Filtering
    if start_season and end_season and start_season != "ALL" and end_season != "ALL":
        s_min = min(start_season, end_season)
        s_max = max(start_season, end_season)
        query = query.filter(and_(Match.season >= s_min, Match.season <= s_max))
    elif start_season and start_season != "ALL":
        query = query.filter(Match.season >= start_season)
    elif end_season and end_season != "ALL":
        query = query.filter(Match.season <= end_season)
    elif season and season != "ALL":
        query = query.filter(Match.season == season)

    # Filter by specific matchday round if provided
    if matchday is not None and matchday > 0:
        query = query.filter(Match.matchday == matchday)

    t1 = team1 or team
    t2 = team2

    if t1 and t1 == "ALL":
        t1 = None
    if t2 and t2 == "ALL":
        t2 = None

    # Both Team 1 and Team 2 selected (Head-to-Head mode)
    if t1 and t2:
        if venue_role == "home":
            query = query.filter(and_(Match.home_team == t1, Match.away_team == t2))
        elif venue_role == "away":
            query = query.filter(and_(Match.home_team == t2, Match.away_team == t1))
        else:
            query = query.filter(
                or_(
                    and_(Match.home_team == t1, Match.away_team == t2),
                    and_(Match.home_team == t2, Match.away_team == t1),
                )
            )
    elif t1:
        if venue_role == "home":
            query = query.filter(Match.home_team == t1)
        elif venue_role == "away":
            query = query.filter(Match.away_team == t1)
        else:
            query = query.filter(or_(Match.home_team == t1, Match.away_team == t1))

    if home_team and home_team != "ALL":
        query = query.filter(Match.home_team == home_team)

    if away_team and away_team != "ALL":
        query = query.filter(Match.away_team == away_team)

    all_matching_rows = query.order_by(Match.match_date.desc()).all()

    # Filter by Standing Ranks (Prev Finish & Pre-Match In-Season Rank)
    has_rank_filters = any([
        home_prev_filter and home_prev_filter != "ALL",
        away_prev_filter and away_prev_filter != "ALL",
        home_pre_filter and home_pre_filter != "ALL",
        away_pre_filter and away_pre_filter != "ALL",
    ])

    filtered_rows = []
    enriched_match_data = []

    # Pre-fetch all logos to avoid N+1 queries during loop
    all_teams_meta = db.query(Team).all()
    logo_map = {t.name: t.logo_path for t in all_teams_meta}

    def format_status(status_str, rank):
        if rank: return f"#{rank}"
        if status_str == "STAYED": return "N/A"
        if status_str == "PROMOTED_FROM_CHAMPIONSHIP": return "Promoted"
        if status_str == "RELEGATED_FROM_EPL": return "Relegated"
        return "Promoted"

    for m in all_matching_rows:
        # Construct UI strings directly from the pre-computed Enriched DB columns

        h_prev_rank_str = format_status(m.home_prev_league_status, m.home_prev_rank)
        a_prev_rank_str = format_status(m.away_prev_league_status, m.away_prev_rank)

        h_pre_rank_str = f"#{m.home_pre_rank}" if m.home_pre_rank else "MD 1"
        a_pre_rank_str = f"#{m.away_pre_rank}" if m.away_pre_rank else "MD 1"

        # Booleans for Rank Filter predicates
        h_is_promoted = (m.home_prev_league_status != "STAYED" and m.home_prev_rank is None)
        a_is_promoted = (m.away_prev_league_status != "STAYED" and m.away_prev_rank is None)

        # Apply Rank Filter predicates
        if has_rank_filters:
            if not match_rank_filter(m.home_prev_rank, h_is_promoted, home_prev_filter):
                continue
            if not match_rank_filter(m.away_prev_rank, a_is_promoted, away_prev_filter):
                continue
            if not match_rank_filter(m.home_pre_rank, False, home_pre_filter):
                continue
            if not match_rank_filter(m.away_pre_rank, False, away_pre_filter):
                continue

        filtered_rows.append(m)
        enriched_match_data.append({
            "id": m.id,
            "season": m.season,
            "matchday": m.matchday,
            "match_date": m.match_date.strftime("%m/%d/%Y") if m.match_date else None,
            "home_team": m.home_team,
            "home_logo": logo_map.get(m.home_team) or "/static/images/crests/generic.png",
            "home_prev_rank": h_prev_rank_str,
            "home_pre_rank": h_pre_rank_str,
            "away_team": m.away_team,
            "away_logo": logo_map.get(m.away_team) or "/static/images/crests/generic.png",
            "away_prev_rank": a_prev_rank_str,
            "away_pre_rank": a_pre_rank_str,
            "hthg": m.hthg,
            "htag": m.htag,
            "htr": m.htr,
            "fthg": m.fthg,
            "ftag": m.ftag,
            "ftr": m.ftr,
        })

    total_count = len(filtered_rows)

    # Calculate Empirical HT and FT Statistics across filtered rows
    if total_count > 0:
        # 1. Half-Time (HT) Outcomes
        ht_home = sum(1 for m in filtered_rows if (m.hthg or 0) > (m.htag or 0))
        ht_draw = sum(1 for m in filtered_rows if (m.hthg or 0) == (m.htag or 0))
        ht_away = sum(1 for m in filtered_rows if (m.htag or 0) > (m.hthg or 0))
        ht_btts = sum(1 for m in filtered_rows if (m.hthg or 0) > 0 and (m.htag or 0) > 0)

        ht_g0 = sum(1 for m in filtered_rows if ((m.hthg or 0) + (m.htag or 0)) == 0)
        ht_g1 = sum(1 for m in filtered_rows if ((m.hthg or 0) + (m.htag or 0)) == 1)
        ht_g2 = sum(1 for m in filtered_rows if ((m.hthg or 0) + (m.htag or 0)) == 2)
        ht_g3plus = sum(1 for m in filtered_rows if ((m.hthg or 0) + (m.htag or 0)) >= 3)

        ht_home_g0 = sum(1 for m in filtered_rows if (m.hthg or 0) == 0)
        ht_home_g1 = sum(1 for m in filtered_rows if (m.hthg or 0) == 1)
        ht_home_g2 = sum(1 for m in filtered_rows if (m.hthg or 0) == 2)
        ht_home_g3plus = sum(1 for m in filtered_rows if (m.hthg or 0) >= 3)

        ht_away_g0 = sum(1 for m in filtered_rows if (m.htag or 0) == 0)
        ht_away_g1 = sum(1 for m in filtered_rows if (m.htag or 0) == 1)
        ht_away_g2 = sum(1 for m in filtered_rows if (m.htag or 0) == 2)
        ht_away_g3plus = sum(1 for m in filtered_rows if (m.htag or 0) >= 3)

        # 2. Full-Time (FT) Outcomes
        ft_home = sum(1 for m in filtered_rows if (m.fthg or 0) > (m.ftag or 0))
        ft_draw = sum(1 for m in filtered_rows if (m.fthg or 0) == (m.ftag or 0))
        ft_away = sum(1 for m in filtered_rows if (m.ftag or 0) > (m.fthg or 0))
        ft_btts = sum(1 for m in filtered_rows if (m.fthg or 0) > 0 and (m.ftag or 0) > 0)

        ft_g0 = sum(1 for m in filtered_rows if ((m.fthg or 0) + (m.ftag or 0)) == 0)
        ft_g1 = sum(1 for m in filtered_rows if ((m.fthg or 0) + (m.ftag or 0)) == 1)
        ft_g2 = sum(1 for m in filtered_rows if ((m.fthg or 0) + (m.ftag or 0)) == 2)
        ft_g3plus = sum(1 for m in filtered_rows if ((m.fthg or 0) + (m.ftag or 0)) >= 3)

        ft_home_g0 = sum(1 for m in filtered_rows if (m.fthg or 0) == 0)
        ft_home_g1 = sum(1 for m in filtered_rows if (m.fthg or 0) == 1)
        ft_home_g2 = sum(1 for m in filtered_rows if (m.fthg or 0) == 2)
        ft_home_g3plus = sum(1 for m in filtered_rows if (m.fthg or 0) >= 3)

        ft_away_g0 = sum(1 for m in filtered_rows if (m.ftag or 0) == 0)
        ft_away_g1 = sum(1 for m in filtered_rows if (m.ftag or 0) == 1)
        ft_away_g2 = sum(1 for m in filtered_rows if (m.ftag or 0) == 2)
        ft_away_g3plus = sum(1 for m in filtered_rows if (m.ftag or 0) >= 3)

        stats = {
            "ht": {
                "home_win": f"{round((ht_home / total_count) * 100, 1)}%",
                "draw": f"{round((ht_draw / total_count) * 100, 1)}%",
                "away_win": f"{round((ht_away / total_count) * 100, 1)}%",
                "btts": f"{round((ht_btts / total_count) * 100, 1)}%",
                "g0": f"{round((ht_g0 / total_count) * 100, 1)}%",
                "g1": f"{round((ht_g1 / total_count) * 100, 1)}%",
                "g2": f"{round((ht_g2 / total_count) * 100, 1)}%",
                "g3plus": f"{round((ht_g3plus / total_count) * 100, 1)}%",
                "home_g0": f"{round((ht_home_g0 / total_count) * 100, 1)}%",
                "home_g1": f"{round((ht_home_g1 / total_count) * 100, 1)}%",
                "home_g2": f"{round((ht_home_g2 / total_count) * 100, 1)}%",
                "home_g3plus": f"{round((ht_home_g3plus / total_count) * 100, 1)}%",
                "away_g0": f"{round((ht_away_g0 / total_count) * 100, 1)}%",
                "away_g1": f"{round((ht_away_g1 / total_count) * 100, 1)}%",
                "away_g2": f"{round((ht_away_g2 / total_count) * 100, 1)}%",
                "away_g3plus": f"{round((ht_away_g3plus / total_count) * 100, 1)}%",
            },
            "ft": {
                "home_win": f"{round((ft_home / total_count) * 100, 1)}%",
                "draw": f"{round((ft_draw / total_count) * 100, 1)}%",
                "away_win": f"{round((ft_away / total_count) * 100, 1)}%",
                "btts": f"{round((ft_btts / total_count) * 100, 1)}%",
                "g0": f"{round((ft_g0 / total_count) * 100, 1)}%",
                "g1": f"{round((ft_g1 / total_count) * 100, 1)}%",
                "g2": f"{round((ft_g2 / total_count) * 100, 1)}%",
                "g3plus": f"{round((ft_g3plus / total_count) * 100, 1)}%",
                "home_g0": f"{round((ft_home_g0 / total_count) * 100, 1)}%",
                "home_g1": f"{round((ft_home_g1 / total_count) * 100, 1)}%",
                "home_g2": f"{round((ft_home_g2 / total_count) * 100, 1)}%",
                "home_g3plus": f"{round((ft_home_g3plus / total_count) * 100, 1)}%",
                "away_g0": f"{round((ft_away_g0 / total_count) * 100, 1)}%",
                "away_g1": f"{round((ft_away_g1 / total_count) * 100, 1)}%",
                "away_g2": f"{round((ft_away_g2 / total_count) * 100, 1)}%",
                "away_g3plus": f"{round((ft_away_g3plus / total_count) * 100, 1)}%",
            },
        }
    else:
        empty = {
            "home_win": "0%", "draw": "0%", "away_win": "0%", "btts": "0%",
            "g0": "0%", "g1": "0%", "g2": "0%", "g3plus": "0%",
            "home_g0": "0%", "home_g1": "0%", "home_g2": "0%", "home_g3plus": "0%",
            "away_g0": "0%", "away_g1": "0%", "away_g2": "0%", "away_g3plus": "0%",
        }
        stats = {"ht": empty, "ft": empty}

    # Paginated slice for the table view
    paginated_results = enriched_match_data[offset : offset + limit]

    return {
        "total_count": total_count,
        "returned_count": len(paginated_results),
        "limit": limit,
        "offset": offset,
        "stats": stats,
        "matches": paginated_results,
    }


@router.get("/calculate")
def calculate_fixture_scenario(
    home_team: str,
    away_team: str,
    league: Optional[str] = None,
    form_window: int = 5,
    h2h_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_request),
):
    """Calculates empirical scenario probabilities for a home vs away fixture using live database records."""
    query = db.query(Match).filter(Match.status == "COMPLETED")
    
    if league and league != "ALL":
        query = query.filter(Match.league == league)

    if h2h_only:
        query = query.filter(
            or_(
                (Match.home_team == home_team) & (Match.away_team == away_team),
                (Match.home_team == away_team) & (Match.away_team == home_team),
            )
        )
    else:
        query = query.filter(
            or_(
                Match.home_team == home_team,
                Match.away_team == home_team,
                Match.home_team == away_team,
                Match.away_team == away_team,
            )
        )

    matches = query.order_by(Match.match_date.desc()).limit(form_window).all()

    if not matches:
        matches = db.query(Match).filter(Match.status == "COMPLETED").order_by(Match.match_date.desc()).limit(form_window).all()

    total = len(matches)
    if total == 0:
        return {
            "fixture": f"{home_team} vs {away_team}",
            "sample_size": 0,
            "metrics": {
                "prob_over_0_5_ht": "0%",
                "prob_over_1_5_ht": "0%",
                "prob_btts_ht": "0%",
                "prob_home_win_ht": "0%",
            },
            "matches": [],
        }

    over_05_ht = sum(1 for m in matches if ((m.hthg or 0) + (m.htag or 0)) > 0)
    over_15_ht = sum(1 for m in matches if ((m.hthg or 0) + (m.htag or 0)) > 1)
    btts_ht = sum(1 for m in matches if (m.hthg or 0) > 0 and (m.htag or 0) > 0)
    home_lead_ht = sum(1 for m in matches if (m.hthg or 0) > (m.htag or 0))

    match_list = []
    for m in matches:
        ht_total = (m.hthg or 0) + (m.htag or 0)
        match_list.append({
            "id": m.id,
            "season": m.season,
            "matchday": m.matchday,
            "match_date": m.match_date.strftime("%m/%d/%Y") if m.match_date else None,
            "home_team": m.home_team,
            "away_team": m.away_team,
            "ht_score": f"{m.hthg or 0} - {m.htag or 0}",
            "ft_score": f"{m.fthg or 0} - {m.ftag or 0}",
            "ht_goals": ht_total,
            "ht_breakdown": f"Over 0.5 HT ({ht_total} Goals)" if ht_total > 0 else "0 Goals in HT",
        })

    return {
        "fixture": f"{home_team} vs {away_team}",
        "form_window": form_window,
        "h2h_only": h2h_only,
        "sample_size": total,
        "metrics": {
            "prob_over_0_5_ht": f"{round((over_05_ht / total) * 100)}%",
            "prob_over_1_5_ht": f"{round((over_15_ht / total) * 100)}%",
            "prob_btts_ht": f"{round((btts_ht / total) * 100)}%",
            "prob_home_win_ht": f"{round((home_lead_ht / total) * 100)}%",
        },
        "matches": match_list,
    }
