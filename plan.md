# Scrollarr Development Plan

This document outlines the roadmap for evolving Scrollarr into a full-featured "Arr"-style application (like Sonarr or Radarr) for monitoring, downloading, and organizing web-based serial fiction.

## Phase 1: Architecture & Stability (Immediate Priority)

Before adding complex features, we must ensure the foundation is robust.

1.  ~~**Unify Background Workers**~~
    -   ~~**Problem:** Currently, `worker.py` runs a continuous loop while `scheduler.py` runs interval checks. This splits logic and makes management difficult.~~
    -   ~~**Solution:** Refactor to use a single `JobManager` (via `APScheduler`) within `app.py`. Remove the standalone `worker.py` loop. All tasks (checking updates, downloading chapters) should be scheduled jobs.~~
2.  ~~**Database Migrations**~~
    -   ~~**Problem:** Schema changes are currently manual (`migrate_db` in `database.py`).~~
    -   ~~**Solution:** Implement `Alembic` for proper database migrations to handle future schema changes safely.~~
3.  ~~**Logging & Error Handling**~~
    -   ~~**Problem:** Logs are scattered.~~
    -   ~~**Solution:** Centralize logging to a file and the console. Expose logs in the UI later.~~

## Phase 2: Core "Arr" Features (Short Term)

These features bring Scrollarr closer to the expected functionality of Sonarr/Radarr.

4.  ~~**Enhanced Metadata (The "Indexer" Aspect)**~~
    -   ~~**Feature:** Store rich metadata for stories.~~
    -   ~~**Implementation:**~~
        -   ~~Add `description`, `tags`, `rating`, `language`, `status` (Completed/Ongoing/Hiatus/Dropped) to the `Story` table.~~
        -   ~~Update scrapers (`RoyalRoadSource`, `AO3Source`) to fetch this data.~~
        -   ~~Display this metadata in the Story Details UI.~~
5.  **Search & Discovery (The "Search" Tab)**
    -   **Feature:** Allow users to search for new content within the app, rather than pasting URLs.
    -   **Implementation:**
        -   Add a `search(query)` method to `BaseSource`.
        -   Implement search scraping for Royal Road and AO3.
        -   Create a "Search" page in the UI to query providers and "Add" stories directly from results.
6.  **Activity & Queue Management (The "Activity" Tab)**
    -   **Feature:** View current downloads, history, and failures.
    -   **Implementation:**
        -   Create a `DownloadHistory` table.
        -   Build an "Activity" page showing:
            -   **Queue:** Currently downloading chapters with progress (if possible) or status.
            -   **History:** List of recently downloaded/failed chapters with timestamps.
        -   Add "Retry" button for failed downloads.
7.  **Manual Interaction (The "Interactive Search")**
    -   **Feature:** Manually trigger a search/update for a specific story or chapter.
    -   **Implementation:** Add "Search for Updates" and "Force Download" buttons on the Story Details page.

## Phase 3: Advanced Organization & Customization (Medium Term)

8.  **Ebook Profiles (The "Quality Profile")**
    -   **Feature:** Customize the output format and style.
    -   **Implementation:**
        -   Create a `Profile` model (e.g., "Kindle", "Kobo", "Tablet").
        -   Settings for: Font size, margins, cover style, output format (EPUB is default, maybe add PDF/MOBI conversion tools).
        -   Assign a profile to a story.
9.  **Library Management & File Organization**
    -   **Feature:** Better file naming and organization.
    -   **Implementation:**
        -   Allow customizable renaming patterns (e.g., `{Author} - {Title}/{Title} - {Chapter Index} - {Chapter Title}.epub`).
        -   Move files to a final "Library" directory (separate from "Downloads").
        -   Handle "Volumes" or "Seasons" more explicitly in the UI.
10. **Notifications**
    -   **Feature:** Alert users on events.
    -   **Implementation:**
        -   Support for Webhooks (Discord, Slack, Gotify).
        -   Triggers: "On Download", "On Upgrade", "On Failure".

## Phase 4: Polish & Ecosystem (Long Term)

11. **Calendar / Upcoming**
    -   **Feature:** View release schedule.
    -   **Implementation:** Infer release schedule from past chapter dates (e.g., "Usually updates on Mondays") and display a calendar view.
12. **System Status**
    -   **Feature:** Health checks.
    -   **Implementation:** UI page showing disk space, database size, provider status (latency/errors).
13. **User Management**
    -   **Feature:** Multi-user support.
    -   **Implementation:** Simple auth (username/password) if exposing to the web.
14. **Import Existing Library**
    -   **Feature:** Scan a directory for existing EPUBs/stories and add them to DB.
