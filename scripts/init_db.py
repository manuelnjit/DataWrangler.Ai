"""DataWrangler.AI - Database Initialization Script.

Creates all required SQLite tables and schemas if they don't already exist.
This is explicitly designed to be run during CI/CD build phases (like Render.com) 
before the FastAPI server actually starts or before any ingestion scripts run.
"""

import sys
import os

# Ensure the root project directory is in the Python path so it can find the 'app' module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine, Base
import app.models  # Ensures models are imported so SQLAlchemy knows about them

def init_db():
    print("Initializing database schemas...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

    # Ensure 'league' column exists in matches table for multi-league support (migrated from main.py)
    from sqlalchemy import text
    with engine.connect() as conn:
        column_info = conn.execute(text("PRAGMA table_info(matches)")).fetchall()
        if not any(col[1] == 'league' for col in column_info):
            conn.execute(text("ALTER TABLE matches ADD COLUMN league VARCHAR(20) NOT NULL DEFAULT 'EPL'"))
            conn.commit()
            print("Migrated matches table to include 'league' column.")

if __name__ == "__main__":
    init_db()
