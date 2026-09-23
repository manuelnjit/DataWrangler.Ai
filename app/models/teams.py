"""EPL Quant API - Team Database Model.

This module defines the `Team` SQLAlchemy ORM table schema used to store
football club metadata, particularly team names and their official crest logos.

Design Decisions:
-----------------
1. Normalized Names: The `name` field directly corresponds to the `home_team` 
   and `away_team` string identifiers in the `Match` model.
2. Local Logo Storage: Due to aggressive CDN hotlinking protection by official
   sites (Premier League, EFL), `logo_path` stores local filesystem paths 
   (e.g., '/static/images/crests/arsenal.png') rather than remote URLs to 
   guarantee 100% uptime and bypass Cloudflare bot protections.
"""

from sqlalchemy import Column, Integer, String
from app.db.database import Base


class Team(Base):
    """SQLAlchemy ORM Model representing a Football Club Entity.

    Table Name:
        `teams`
        
    Attributes:
        id (int): Primary Key.
        name (str): Normalized string representing the club (e.g. 'Arsenal').
            Matches strings found in matches.home_team.
        logo_path (str): The local URL path to the crest image.
    """

    __tablename__ = "teams"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Core Attributes
    name = Column(String(100), unique=True, nullable=False, index=True)
    logo_path = Column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name='{self.name}', logo_path='{self.logo_path}')>"
