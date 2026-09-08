import asyncio
import os
import sys

# Add the root project directory to sys.path so we can import 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.ingestion.football_data import FootballDataIngestor

async def main():
    db = SessionLocal()
    try:
        ingestor = FootballDataIngestor(timeout_seconds=30.0)
        print("Starting Championship historical data ingestion...")
        stats = await ingestor.ingest_all_historical_seasons(db=db, csv_code="E1", league="Championship")
        print(f"Ingestion completed: {stats}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
