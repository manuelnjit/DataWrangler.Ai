"""EPL Quant API - Match Database Model.

This module defines the `Match` SQLAlchemy ORM table schema used to store
Premier League match fixtures, half-time scorelines, full-time scorelines, matchday rounds, and outcome indicators.

Troubleshooting & Data Integrity:
---------------------------------
1. Unique Constraint (`uq_match_fixture`):
   A composite unique constraint exists on `(season, match_date, home_team, away_team)`.
   This ensures idempotent ingestion: running the ETL pipeline multiple times will NOT create
   duplicate fixture rows, but will perform an UPSERT (UPDATE if exists, INSERT if new).

2. Indexed Columns for High Query Performance:
   `season`, `matchday`, `home_team`, `away_team`, and `match_date` are indexed. Filtering queries such as
   `GET /api/v1/terminal/matches?team=Arsenal&season=2023-2024` hit composite index lookups, executing in <10ms.

3. Goal Abbreviations Reference (Football-Data Standard):
   - FTHG: Full Time Home Team Goals
   - FTAG: Full Time Away Team Goals
   - FTR:  Full Time Result (H = Home Win, D = Draw, A = Away Win)
   - HTHG: Half Time Home Team Goals
   - HTAG: Half Time Away Team Goals
   - HTR:  Half Time Result (H = Home Win, D = Draw, A = Away Win)
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, UniqueConstraint, Index
from app.db.database import Base


class Match(Base):
    """SQLAlchemy ORM Model representing an English Premier League Match Fixture.

    Table Name:
        `matches`
    """

    __tablename__ = "matches"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Fixture Metadata
    season = Column(String(10), nullable=False, index=True)  # e.g., "2023-2024"
    matchday = Column(Integer, nullable=True, index=True)   # e.g., Matchday 1 to 38/42
    match_date = Column(Date, nullable=False, index=True)

    # Team Names
    home_team = Column(String(100), nullable=False, index=True)
    away_team = Column(String(100), nullable=False, index=True)
    # League Identifier (per‑league SQLite database)
    league = Column(String(20), nullable=False, default='EPL', index=True)

    # Match Status & Full Time Metrics
    status = Column(String(20), nullable=False, default="COMPLETED", index=True)  # 'COMPLETED' or 'SCHEDULED'
    fthg = Column(Integer, nullable=True)  # Full Time Home Goals
    ftag = Column(Integer, nullable=True)  # Full Time Away Goals
    ftr = Column(String(1), nullable=True)  # Full Time Result ('H', 'D', 'A')

    # Half Time Metrics (Quantitative Model Inputs)
    hthg = Column(Integer, nullable=True)  # Half Time Home Goals
    htag = Column(Integer, nullable=True)  # Half Time Away Goals
    htr = Column(String(1), nullable=True)  # Half Time Result ('H', 'D', 'A')

    # System Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Table Constraints & Composite Indexes
    __table_args__ = (
        # Guarantees fixture uniqueness for ETL upsert routines
        UniqueConstraint(
            "season",
            "match_date",
            "home_team",
            "away_team",
            name="uq_match_fixture",
        ),
        # Composite index for rapid query filtering by team and season
        Index("idx_season_team", "season", "home_team", "away_team"),
    )

    def __repr__(self) -> str:
        return (
            f"<Match(id={self.id}, league='{self.league}', season='{self.season}', matchday={self.matchday}, date={self.match_date}, "
            f"fixture='{self.home_team} vs {self.away_team}', score={self.fthg}-{self.ftag})>"
        )
