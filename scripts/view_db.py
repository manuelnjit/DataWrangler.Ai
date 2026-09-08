"""DataWrangler.AI - Database Inspection Utility.

Run this script from your terminal to inspect all tables and query records stored in `epl_quant.db`.

Usage:
    python3 scripts/view_db.py
"""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SessionLocal, engine
from app.models.users import User
from app.models.matches import Match
from app.models.api_keys import APIKey
from sqlalchemy import inspect


def inspect_database():
    """Prints database tables, schemas, and row counts formatted nicely in console."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print("\n" + "=" * 60)
    print(" 🗄️  DATAWRANGLER.AI DATABASE INSPECTOR (epl_quant.db)")
    print("=" * 60)
    print(f" Detected Tables: {', '.join(tables)}\n")

    db = SessionLocal()
    try:
        # 1. Users Table
        print("── 👤 USERS TABLE ('users') ──────────────────────────────────")
        users = db.query(User).all()
        if not users:
            print("  (No user accounts registered yet)")
        else:
            for u in users:
                print(f"  • ID: {u.id} | Name: '{u.full_name}' | Email: '{u.email}' | Status: '{u.subscription_status}' | Registered: {u.created_at.strftime('%Y-%m-%d %H:%M')}")
        print()

        # 2. Matches Table
        print("── ⚽ MATCHES TABLE ('matches') ──────────────────────────────")
        matches_count = db.query(Match).count()
        print(f"  • Total Fixtures Stored: {matches_count}")
        sample_matches = db.query(Match).limit(5).all()
        if sample_matches:
            print("  • Sample Records (First 5):")
            for m in sample_matches:
                print(f"    [{m.season} | {m.match_date}] {m.home_team} vs {m.away_team} -> HT: {m.hthg}-{m.htag} ({m.htr}) | FT: {m.fthg}-{m.ftag} ({m.ftr})")
        print()

        # 3. API Keys Table
        print("── 🔑 API KEYS TABLE ('api_keys') ────────────────────────────")
        keys_count = db.query(APIKey).count()
        print(f"  • Total API Keys Issued: {keys_count}")
        print("=" * 60 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    inspect_database()
