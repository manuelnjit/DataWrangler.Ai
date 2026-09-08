# Implementation Plan - DataWrangler.AI

Build a production-ready Minimum Viable Product (MVP) web application for **DataWrangler.AI** — the "Bloomberg Terminal for Sports Betting".

---

## 🎯 Core Product & Security Architecture

1. **Free User Registration & Authentication**: Users register with full name, email, and password. Passwords are salted and hashed using `bcrypt`.
2. **Secure Session Cookie Management**:
   - `HttpOnly`: Prevents client-side JavaScript from accessing session tokens.
   - `Secure`: Ensures HTTPS transmission in production environments.
   - `SameSite=Lax`: Guards against Cross-Site Request Forgery (CSRF).
3. **Protected Terminal Workspace (`/dashboard`)**:
   - `/`: Public landing page showcasing value proposition & interactive demo.
   - Auth Modal: Integrated `Log In` and `Create Account` tabbed dialog.
   - `/dashboard`: Protected sports terminal workspace for authenticated subscribers.
4. **Product Backlog & Feature Roadmap**: Tracked internally in **[docs/product_roadmap_backlog.md](file:///Users/manuelnavas/Documents/Google-Antigravity/Getting-started/docs/product_roadmap_backlog.md)**.

---

## 📋 Task Checklist & Milestone Progress

### Phase 1: Landing Page & Terminal UI Layout
- [x] Create core HTML/CSS layout structure with responsive design tokens.
- [x] Build `app/static/index.html`: DataWrangler.AI landing page with Copilot Purple (`#8957e5`) & Magenta (`#f472b6`) styling.
- [x] Configure root routes in `app/main.py`.

### Phase 2: Configuration Engine & Database ORM Schema
- [x] `app/core/config.py`: Environment configuration via Pydantic Settings (`DATABASE_URL`, `JWT_SECRET_KEY`).
- [x] `app/db/database.py`: SQLAlchemy database engine, `SessionLocal` factory, and `get_db()` dependency.
- [x] `app/models/matches.py`: EPL match ORM schema (`matches` table) with `matchday` column and composite constraint `uq_match_fixture`.
- [x] `app/models/users.py`: User account schema with hashed password support (`users` table).
- [x] `app/models/api_keys.py`: API key credentials schema.

### Phase 3: Authentication Core & Session Cookie Middleware
- [x] Update `app/models/users.py` to include `full_name` and `hashed_password` fields.
- [x] `app/core/security.py`: Password hashing (`bcrypt`) and signed JWT token engine.
- [x] `app/schemas/auth.py`: Pydantic validation contracts (`UserRegister`, `UserLogin`, `UserOut`).
- [x] `app/api/v1/auth.py`: Endpoints (`POST /register`, `POST /login`, `POST /logout`, `GET /me`).
- [x] Configure `HttpOnly`, `SameSite=Lax` session cookie handler.
- [x] Create `app/static/dashboard.html`: Protected terminal UI verifying session status on boot.

### Phase 4: Data Ingestion Pipeline (33-Season Historical EPL ETL Engine)
- [x] **Task 4.1: ETL Fetching Module (`app/ingestion/football_data.py`)**:
  - Build `FootballDataIngestor` class using `httpx` async client.
  - Multi-season URL generator for 33 historical seasons (`1993-1994` through `2025-2026`).
- [x] **Task 4.2: Data Cleaning & Normalization Engine**:
  - Implement date parsing outputting strict `MM/DD/YYYY` (e.g. `08/11/2023`).
  - Add explicit `season` column (e.g. `'1999-2000'`, `'2025-2026'`).
  - Add `matchday` calculation engine ranking chronological team fixture rounds (Matchday 1 to 38/42).
  - Implement team name normalizer dictionary covering 3 decades of Premier League clubs.
  - Extract and validate scorelines (`FTHG`, `FTAG`, `FTR`, `HTHG`, `HTAG`, `HTR`).
- [x] **Task 4.3: Idempotent Database UPSERT Engine**:
  - Implement match lookup by constraint `(season, match_date, home_team, away_team)`.
  - Ingest 33 seasons of historical data (**verified 12,704 matches stored and backfilled with matchday**).
- [ ] **Task 4.4: Ingestion CLI & Automated Scheduler**:
  - Standalone CLI execution (`python3 -m app.ingestion.football_data --seasons all`).
  - Automated bi-weekly update trigger (Mondays & Thursdays post-fixture rounds).

### Phase 4.5: Standings Engine, Standing Rank Filters & Clear All Filters Button
- [x] **Task 4.5.1: Matchday-by-Matchday Standings Endpoint (`GET /api/v1/terminal/standings`)**:
  - Computes live standings (Pos, P, W, D, L, GF, GA, GD, Pts) for any season up to any target Matchday round.
  - Prior Season Rank lookup (e.g., `#1`, `#2`, `#17`) with automatic **`PROMOTED`** tag attribution for Championship promoted teams.
- [x] **Task 4.5.2: In-Season Pre-Match Standing Rank Calculation**:
  - Computes live league table rank of home & away teams going into each match (`Home Rank Going In`, `Away Rank Going In`).
- [x] **Task 4.5.3: Standing Rank Filters**:
  - Added 4 Standing Rank Filter controls to Raw SQL filter bar: `Home Prev Finish`, `Away Prev Finish`, `Home Rank Going In`, `Away Rank Going In`.
- [x] **Task 4.5.4: Clear All Filters Button**:
  - Added **`🧹 Clear All Filters`** button instantly resetting all 9 dropdowns, venue roles, and season presets back to baseline defaults.

### Phase 5: Security Hardening & Production Launch
- [ ] Configure CORS middleware in `app/main.py` with explicit allowed origins.
- [ ] Add rate-limiting middleware to auth endpoints (`/login`, `/register`).
- [ ] Set up production deployment configuration file (`render.yaml` or Procfile).

---

## 🧪 Verification Plan

### Automated Tests
- Verification script loading `app.main` cleanly with Clear All Filters button.

### Manual Verification
- Open `/dashboard` in browser, set multiple filters (e.g. Arsenal vs Chelsea, Top 4 Prev Finish), then click **`🧹 Clear All Filters`** and verify all dropdowns return to "All" and the database resets to full 12,704 matches view!
