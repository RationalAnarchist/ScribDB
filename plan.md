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

## Active Roadmap

### Phase 3: Advanced Organization (Completion)

#### 1. Notifications System
- **Goal:** Alert users via Webhooks (Discord/Slack) on events.
- **Tasks:**
    1.  Create `notification_manager.py` with `Notifier` class.
    2.  Add `discord_webhook_url` to `config.json` and `Settings` model.
    3.  Implement `send_notification(message, type)` method.
    4.  Integrate with `JobManager`:
        -   Alert on "Download Started/Finished/Failed".
        -   Alert on "New Chapters Found".
    5.  Add UI settings for Webhook URL and a "Test" button.

### Phase 4: Polish & Ecosystem

#### 2. Release Calendar & Smart Scheduling
- **Goal:** Track publication dates to predict releases.
- **Tasks:**
    1.  **Database Migration:** Add `published_date` column to `Chapter` table.
    2.  **Scraper Updates:** Update `RoyalRoadSource` and `AO3Source` to parse dates.
    3.  **Logic:** Implement `predict_next_chapter(story_id)` based on history.
    4.  **UI:** Create `/calendar` page showing past releases and predicted future ones.

#### 3. System Status Dashboard
- **Goal:** Monitor application health.
- **Tasks:**
    1.  Create `/status` endpoint.
    2.  Implement checks for:
        -   Disk Usage (Free/Total).
        -   Database Size.
        -   Memory Usage.
    3.  Add Log Viewer widget (tail `scrollarr.log`).

#### 4. Library Import
- **Goal:** Import existing EPUBs.
- **Tasks:**
    1.  Create "Import" page.
    2.  Implement file scanner/uploader.
    3.  Use `ebooklib` to extract metadata (Title, Author).
    4.  Match against Providers to resume monitoring.
