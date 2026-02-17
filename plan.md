# Scrollarr Development Plan

This document outlines the roadmap for evolving Scrollarr into a full-featured "Arr"-style application (like Sonarr or Radarr) for monitoring, downloading, and organizing web-based serial fiction.

## Completed Phases

### Phase 1: Architecture & Stability
- [x] Unify Background Workers (JobManager)
- [x] Database Migrations (Alembic)
- [x] Logging & Error Handling

### Phase 2: Core "Arr" Features
- [x] Enhanced Metadata (Description, Tags, Rating, etc.)
- [x] Search & Discovery (UI & Logic)
- [x] Activity & Queue Management
- [x] Manual Interaction (Update/Retry)

### Phase 3: Advanced Organization & Customization (Partial)
- [x] Ebook Profiles
- [x] Library Management (File naming, organization)
- [x] Alert users via webhooks

## Active Roadmap

### Phase 4: Polish & Ecosystem

#### 2. Release Calendar & Smart Scheduling
- **Goal:** Track publication dates to predict releases.
- **Tasks:**
    1.  [x] **Database Migration:** Add `published_date` column to `Chapter` table.
    2.  [x] **Scraper Updates:** Update `RoyalRoadSource` and `AO3Source` to parse dates.
    3.  [x] **Logic:** Implement `predict_next_chapter(story_id)` based on history.
    4.  [x] **UI:** Create `/calendar` page showing past releases and predicted future ones.

#### 3. System Status Dashboard
- **Goal:** Monitor application health.
- **Tasks:**
    1.  [x] Create `/status` endpoint.
    2.  [x] Implement checks for:
        -   [x] Disk Usage (Free/Total).
        -   [x] Database Size.
        -   [x] Memory Usage.
    3.  [x] Add Log Viewer widget (tail `scrollarr.log`).

#### 4. Library Import
- **Goal:** Import existing EPUBs.
- **Tasks:**
    1.  Create "Import" page.
    2.  Implement file scanner/uploader.
    3.  Use `ebooklib` to extract metadata (Title, Author).
    4.  Match against Providers to resume monitoring.

### Refactoring & Cleanup
- **Goal:** Improve code organization, maintainability, and usability.
- **Suggestions:**
    -   **Modularization:** Move core logic (`app.py`, `database.py`, `models.py`) into a dedicated package (e.g., `src/` or `scrollarr/`).
    -   **Configuration:** Centralize configuration loading and consider using environment variables more extensively.
    -   **Dependency Management:** Migrate from `requirements.txt` to `pyproject.toml` or `poetry` for better dependency resolution and dev/prod separation.
    -   **Testing:** Expand unit test coverage and organize tests into a more structured hierarchy.
    -   **Documentation:** Generate API documentation and improve the README.
    -   **Frontend:** Separate frontend assets (templates/static) from backend logic more clearly.
