# DataWrangler.AI - Product Roadmap & Feature Backlog

This document serves as an internal product backlog and strategic roadmap tracking all feature ideas, quantitative analytics enhancements, and future architectural expansions for **DataWrangler.AI**.

---

## 🎯 Product Concept & Value Proposition

**DataWrangler.AI** is a SaaS application designed as a **"Bloomberg Terminal for Sports Betting & Quantitative Football Analytics"**.

Rather than selling generic picks or black-box predictions, DataWrangler.AI provides quantitative sports modelers and handicappers with **empirical historical match probabilities** derived directly from real database records across 32 seasons of data.

---

## 🚀 Current MVP Feature Baseline (Completed)

1. **32-Season Historical EPL Database**: 12,324 Premier League matches (1993 through 2024-2025) normalized and stored in SQLite.
2. **Official 51-Team Crest System**: Official Premier League club crest badges for all 51 historical teams with 2-letter fallback rendering.
3. **Raw SQL Match Terminal**: Interactive spreadsheet-style table with default 25-row pagination, Head-to-Head dual team filters (`Team 1` vs `Team 2`), Option 1 Segmented Venue Perspective Bar (`🌐 All Matches`, `🏠 Home`, `✈️ Away`), and `Load More Matches (+25)` button.
4. **Multi-Season Range Controls & Presets**: From Season and To Season dropdowns plus Quick Season Range Preset buttons (`Last 3`, `Last 5`, `Last 10`, `All 32`).
5. **Filtered Dataset Empirical Statistics Section**: 7 probability metric cards (Home Win %, Draw %, Away Win %, Goals = 0, 1, 2, 3+) with a toggle switch between `⏱️ Half-Time (HT)` and `⚽ Full-Time (FT)` probabilities.
6. **Scenario Calculator**: Pricing tool evaluating form windows (Last 5, Last 10, All Season).
7. **Security & Session Auth**: Password salting/hashing via `bcrypt`, signed JWT tokens, and `HttpOnly` `SameSite=Lax` session cookies.

---

## 💡 Strategic Feature Backlog & Future Roadmap

The following features have been identified as high-value additions for future development cycles:

### 💰 Feature 1: Implied Odds & Value Edge Calculator (`+EV Engine`)
- **Concept**: Convert empirical probabilities (e.g. 50% Home Win) into **Implied Fair Decimal Odds** ($1 / 0.50 = 2.00$).
- **User Experience**: Allow subscribers to enter live bookmaker odds (e.g. DraftKings / Pinnacle odds of $2.20) to automatically calculate and highlight **Positive Expected Value (+EV Edge)**.
- **Priority**: High (Phase 6 Candidate).

---

### ⚽ Feature 2: Both Teams to Score (BTTS) & Goal Line Matrix
- **Concept**: Expand the statistics section with explicit betting market breakdowns:
  - `BTTS Yes %` vs `BTTS No %`
  - `Over 1.5 FT Goals %`, `Over 2.5 FT Goals %`, `Over 3.5 FT Goals %`
  - `HT/FT Double Matrix` (e.g. `Home/Home`, `Draw/Home`, `Away/Home`).
- **Priority**: High.

---

### 📥 Feature 3: 1-Click Raw Dataset Export (CSV / JSON)
- **Concept**: Add an **"Export Filtered SQL View to CSV"** button on the raw database terminal view.
- **User Experience**: Quantitative modelers can download filtered datasets directly into Python (Pandas/Jupyter) or Excel for custom backtesting.
- **Priority**: Medium-High.

---

### 🌍 Feature 4: Multi-League Expansion (La Liga, Serie A, Bundesliga, Ligue 1)
- **Concept**: Extend the ETL engine (`FootballDataIngestor`) to support top European football leagues:
  - 🇪🇸 La Liga (`SP1`)
  - 🇮🇹 Serie A (`I1`)
  - 🇩🇪 Bundesliga (`D1`)
  - 🇫🇷 Ligue 1 (`F1`)
- **Priority**: Medium.

---

### ⭐️ Feature 5: Saved Custom Query Presets & Favorite Matchups
- **Concept**: Allow logged-in subscribers to save named query configurations to their account:
  - Example: *"Man City vs Top 6 at Home (Last 5 Years)"*
  - Example: *"Liverpool Away High-Goal Fixtures"*
- **Priority**: Medium.

---

### 🤖 Feature 6: Ingestion CLI & Automated Scheduler (Task 4.4)
- **Concept**: Standalone CLI execution (`python3 -m app.ingestion.football_data --seasons all`) and automated background scheduler updating database records post-fixture rounds (Mondays & Thursdays).
- **Priority**: Scheduled.

---

### 🔒 Feature 7: Production CORS & Rate-Limiting Security Hardening (Phase 5)
- **Concept**: Configure explicit origin CORS middleware and rate-limiting on auth endpoints (`/login`, `/register`) prior to internet deployment.
- **Priority**: Required before Launch.
