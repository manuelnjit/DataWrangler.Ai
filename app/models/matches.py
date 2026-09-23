"""EPL Quant API - Match Database Model.

This module defines the Bronze (`RawMatch`) and Gold (`EnrichedMatch`) SQLAlchemy ORM table schemas.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, UniqueConstraint, Index
from app.db.database import Base


class RawMatch(Base):
    """Bronze Layer: Untouched match data exactly as pulled from the API."""
    __tablename__ = "raw_matches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    season = Column(String(10), nullable=False, index=True)
    matchday = Column(Integer, nullable=True, index=True)
    match_date = Column(Date, nullable=False, index=True)
    home_team = Column(String(100), nullable=False, index=True)
    away_team = Column(String(100), nullable=False, index=True)
    league = Column(String(20), nullable=False, default='EPL', index=True)

    status = Column(String(20), nullable=False, default="COMPLETED", index=True)
    fthg = Column(Integer, nullable=True)
    ftag = Column(Integer, nullable=True)
    ftr = Column(String(1), nullable=True)
    hthg = Column(Integer, nullable=True)
    htag = Column(Integer, nullable=True)
    htr = Column(String(1), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("season", "match_date", "home_team", "away_team", name="uq_raw_match_fixture"),
        Index("idx_raw_season_team", "season", "home_team", "away_team"),
    )


class EnrichedMatch(Base):
    """Gold Layer: Enriched match data with calculated ranks and stats for UI/ML consumption."""
    __tablename__ = "enriched_matches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Core Data (Same as Raw)
    season = Column(String(10), nullable=False, index=True)
    matchday = Column(Integer, nullable=True, index=True)
    match_date = Column(Date, nullable=False, index=True)
    home_team = Column(String(100), nullable=False, index=True)
    away_team = Column(String(100), nullable=False, index=True)
    league = Column(String(20), nullable=False, default='EPL', index=True)

    status = Column(String(20), nullable=False, default="COMPLETED", index=True)
    fthg = Column(Integer, nullable=True)
    ftag = Column(Integer, nullable=True)
    ftr = Column(String(1), nullable=True)
    hthg = Column(Integer, nullable=True)
    htag = Column(Integer, nullable=True)
    htr = Column(String(1), nullable=True)

    # Gold Enriched Columns (Calculated by rank_calculator.py)
    home_prev_rank = Column(Integer, nullable=True)
    away_prev_rank = Column(Integer, nullable=True)
    
    # "STAYED", "PROMOTED_FROM_CHAMPIONSHIP", "RELEGATED_FROM_EPL", etc.
    home_prev_league_status = Column(String(50), nullable=True, default="STAYED")
    away_prev_league_status = Column(String(50), nullable=True, default="STAYED")
    
    home_pre_rank = Column(Integer, nullable=True)
    away_pre_rank = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("season", "match_date", "home_team", "away_team", name="uq_enriched_match_fixture"),
        Index("idx_enriched_season_team", "season", "home_team", "away_team"),
    )
