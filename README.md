# DataWrangler.AI - Developer Onboarding Guide

Welcome back! This document serves as a quick catch-up guide for **DataWrangler.AI**, the "Bloomberg Terminal for Sports Betting" (currently focused on the English Premier League). It summarizes what the project is, what has been built so far, how to run it locally, and exactly where you left off.

## 🚀 Project Overview
DataWrangler.AI is a SaaS application allowing quantitative sports modelers to interactively calculate empirical probabilities, view matchday-by-matchday historical Premier League standings, and simulate upcoming fixture scenarios.

The tech stack comprises:
- **Backend**: FastAPI (Python)
- **Frontend**: Vanilla HTML/CSS/JS (Landing Page + Protected Dashboard)
- **Database**: SQLite (`epl_quant.db`) with SQLAlchemy ORM
- **Security**: JWT tokens stored in `HttpOnly` cookies, `bcrypt` password hashing

## 📁 Project Architecture & Directory Structure
```text
datawrangler-ai/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py         # JWT and cookie authentication endpoints
│   │       └── terminal.py     # Standings and probability modeling endpoints
│   ├── core/
│   │   ├── config.py           # Environment variables and system settings
│   │   └── security.py         # Password hashing and token generation
│   ├── db/
│   │   └── database.py         # SQLAlchemy engine and get_db() session manager
│   ├── ingestion/
│   │   └── football_data.py    # Async ETL script to scrape and upsert historical matches
│   ├── models/
│   │   ├── matches.py          # SQLAlchemy matches table schema
│   │   └── users.py            # SQLAlchemy users table schema
│   ├── schemas/
│   │   └── auth.py             # Pydantic validation schemas for auth
│   ├── static/
│   │   ├── index.html          # Frontend Landing Page
│   │   └── dashboard.html      # Protected Software Terminal UI
│   └── main.py                 # FastAPI application and route mounting
├── data/
│   └── epl_quant.db            # SQLite Database (Git ignored)
├── docs/
│   ├── IMPLEMENTATION_PLAN.md  # Detailed task checklist and progress
│   └── MARKETING_PLAN.md       # Target audience and beta testing strategy
├── .env                        # Local secret variables (DO NOT COMMIT)
├── .gitignore                  # Tells GitHub what files/folders to ignore
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

## ✅ What's Been Built So Far
We have successfully completed Phases 1 through 4.5 of the Implementation Plan:

1. **Core Application & UI**:
   - `index.html`: Landing page with an integrated Auth modal (Login/Register).
   - `dashboard.html`: The protected software terminal workspace. Theming relies on a custom Copilot Purple and Soft Magenta color scheme.
2. **Authentication**:
   - Secure authentication endpoints (`/api/v1/auth/*`) handling user registration, login, logout, and session verification (`/me`).
3. **Data Ingestion (Historical)**:
   - Built a robust ETL pipeline (`app.ingestion.football_data`) that asynchronously ingests CSV data from Football-Data.co.uk.
   - Successfully parsed, normalized, and ingested **33 historical EPL seasons** (1993-2026), totaling **12,704 matches**.
   - Includes custom logic for normalising team names, extracting matchdays, and identifying previous season standings.
4. **Data Ingestion (Upcoming) & 1-Click Scenarios**:
   - Built an ingestion engine for scheduled upcoming fixtures (`app.ingestion.upcoming_fixtures`), storing **380 scheduled matches**.
   - Added a "1-Click Quant Matchup" feature on the UI to quickly simulate upcoming matches based on historical constraints.
5. **Standings Engine & Terminal APIs**:
   - Advanced APIs built to query historical matches, upcoming fixtures, seasons, and dynamic matchday-by-matchday standings (including PROMOTED tags and prior season ranks).
   - "Clear All Filters" functionality added to the UI to instantly reset to the baseline default view.

## 💻 How to Run the Project Locally

### 1. Run the FastAPI Server
To start the backend server and serve the front-end interface, use `uvicorn`:
```bash
uvicorn app.main:app --reload
```
Once running, you can access the application at [http://localhost:8000/](http://localhost:8000/). The interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Manual Data Ingestion Commands
If you ever need to re-run or test the ingestion pipelines, you can run the following modules as scripts:
- **Upcoming Fixtures:**
  ```bash
  python3 -m app.ingestion.upcoming_fixtures
  ```
- **Historical Matches:**
  ```bash
  python3 -m app.ingestion.football_data
  ```

## 📍 Where to Pick Up From (Your Next Tasks)
You are currently on **Phase 4.4** and heading into **Phase 5 (Production & Security Hardening)**.

### Current Active Task:
- **Task 4.4: Ingestion CLI & Automated Scheduler**
  - Create a cohesive standalone CLI execution entrypoint (e.g., `python3 -m app.ingestion.football_data --seasons all`).
  - Set up an automated scheduler/trigger for bi-weekly data updates (Mondays & Thursdays post-fixture rounds) so the terminal stays fresh with the latest results.

### Upcoming Phase 5 Tasks:
- Configure CORS middleware in `app/main.py` with explicit allowed origins.
- Add rate-limiting middleware to auth endpoints (`/login`, `/register`) to prevent brute-force attacks.
- Set up a production deployment configuration file (e.g., `render.yaml` or a Procfile) for eventual launch.

### Useful Reference Files:
- [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md): Detailed task checklist and architecture goals.
- [ARCHITECTURE_MAP.md](docs/ARCHITECTURE_MAP.md): System topology and request flow diagrams.
- [WALKTHROUGH.md](docs/WALKTHROUGH.md): Audit trail of completed steps and milestones.
