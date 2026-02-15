import logging
import os
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from database import SessionLocal, Story, Chapter, Source, DownloadHistory
from story_manager import StoryManager
from ebook_builder import EbookBuilder
from job_manager import JobManager
from config import config_manager
from logger import setup_logging

# Configure logging
setup_logging(log_level=config_manager.get('log_level'), log_file='logs/scrollarr.log')
logger = logging.getLogger(__name__)

app = FastAPI(title="Scrollarr")

# Templates
templates = Jinja2Templates(directory="templates")

# Initialize StoryManager
try:
    story_manager = StoryManager()
except Exception as e:
    logger.error(f"Failed to initialize StoryManager: {e}")
    story_manager = None

# Dependency for DB Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Models for API
class UrlRequest(BaseModel):
    url: str

class SettingsRequest(BaseModel):
    download_path: str
    min_delay: float = 2.0
    max_delay: float = 5.0
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    update_interval_hours: int = 1
    worker_sleep_min: float = 30.0
    worker_sleep_max: float = 60.0
    database_url: str = "sqlite:///library.db"
    log_level: str = "INFO"

# JobManager instance
job_manager = JobManager()

@app.on_event("startup")
async def startup_event():
    """Start the background job manager."""
    global job_manager
    job_manager.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown the job manager."""
    global job_manager
    if job_manager:
        job_manager.stop()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    """Render the dashboard with all stories."""
    stories = db.query(Story).all()

    stories_with_progress = []
    for story in stories:
        total = len(story.chapters)
        downloaded = sum(1 for c in story.chapters if c.status == 'downloaded')
        progress = (downloaded / total * 100) if total > 0 else 0

        # Add attributes for the template
        story.progress = round(progress, 1)
        story.total_chapters = total
        story.downloaded_chapters = downloaded
        stories_with_progress.append(story)

    return templates.TemplateResponse("index.html", {"request": request, "stories": stories_with_progress})

@app.get("/add", response_class=HTMLResponse)
async def add_new_page(request: Request):
    """Render the add new story page."""
    return templates.TemplateResponse("add_new.html", {"request": request})

@app.get("/activity", response_class=HTMLResponse)
async def activity_page(request: Request):
    """Render the activity page."""
    return templates.TemplateResponse("activity.html", {"request": request})

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render the settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/sources", response_class=HTMLResponse)
async def sources_page(request: Request):
    """Render the sources page."""
    return templates.TemplateResponse("sources.html", {"request": request})

@app.get("/api/queue")
async def get_queue(db: Session = Depends(get_db)):
    """Get pending chapters."""
    # Limit to top 50 to avoid huge response if backlog is large
    pending_chapters = db.query(Chapter).filter(Chapter.status == 'pending').order_by(Chapter.id.asc()).limit(50).all()

    result = []
    for chapter in pending_chapters:
        result.append({
            "id": chapter.id,
            "story_id": chapter.story_id,
            "story_title": chapter.story.title if chapter.story else "Unknown Story",
            "chapter_title": chapter.title,
            "index": chapter.index
        })
    return result

@app.get("/api/history")
async def get_history(db: Session = Depends(get_db)):
    """Get download history."""
    history = db.query(DownloadHistory).order_by(desc(DownloadHistory.timestamp)).limit(100).all()

    result = []
    for h in history:
        result.append({
            "id": h.id,
            "story_title": h.story.title if h.story else "Unknown Story",
            "chapter_title": h.chapter.title if h.chapter else "Unknown Chapter",
            "status": h.status,
            "timestamp": h.timestamp.isoformat() if h.timestamp else None,
            "details": h.details,
            "chapter_id": h.chapter_id
        })
    return result

@app.post("/api/chapter/{chapter_id}/retry")
async def retry_chapter(chapter_id: int, db: Session = Depends(get_db)):
    """Retry a failed chapter."""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    chapter.status = 'pending'
    db.commit()
    return {"message": "Chapter queued for retry"}

@app.get("/api/settings")
async def get_settings():
    """Get current configuration."""
    # Return all config values
    return config_manager.config

@app.post("/api/settings")
async def update_settings(settings: SettingsRequest):
    """Update configuration."""
    try:
        config_manager.set("download_path", settings.download_path)
        config_manager.set("min_delay", settings.min_delay)
        config_manager.set("max_delay", settings.max_delay)
        config_manager.set("user_agent", settings.user_agent)
        config_manager.set("update_interval_hours", settings.update_interval_hours)
        config_manager.set("worker_sleep_min", settings.worker_sleep_min)
        config_manager.set("worker_sleep_max", settings.worker_sleep_max)
        config_manager.set("database_url", settings.database_url)
        config_manager.set("log_level", settings.log_level)

        # Update jobs with new settings
        if job_manager:
            job_manager.update_jobs()

        return {"message": "Settings updated successfully"}
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update settings")

@app.get("/api/sources")
async def get_sources(db: Session = Depends(get_db)):
    """Get all sources."""
    sources = db.query(Source).all()
    return [{"name": s.name, "key": s.key, "is_enabled": s.is_enabled} for s in sources]

@app.post("/api/sources/{source_key}/toggle")
async def toggle_source(source_key: str, db: Session = Depends(get_db)):
    """Toggle a source enabled state."""
    source = db.query(Source).filter(Source.key == source_key).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.is_enabled = not source.is_enabled
    db.commit()

    # Reload providers in story_manager
    if story_manager:
        story_manager.reload_providers()

    return {"message": f"Source {source.name} {'enabled' if source.is_enabled else 'disabled'}", "is_enabled": source.is_enabled}

@app.post("/api/lookup")
async def lookup_story(request: UrlRequest):
    """Lookup story metadata without saving."""
    if not story_manager:
        raise HTTPException(status_code=500, detail="StoryManager not initialized")

    try:
        provider = story_manager.source_manager.get_provider_for_url(request.url)
        if not provider:
            raise HTTPException(status_code=400, detail="Provider not found for this URL")

        metadata = provider.get_metadata(request.url)
        # Ensure values are JSON serializable (sometimes description might be complex, but here it's string)
        return metadata
    except Exception as e:
        logger.error(f"Lookup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/add")
async def add_story(request: UrlRequest):
    """Add a story to the database."""
    if not story_manager:
        raise HTTPException(status_code=500, detail="StoryManager not initialized")

    try:
        story_id = story_manager.add_story(request.url)
        return {"story_id": story_id, "message": "Story added successfully"}
    except Exception as e:
        logger.error(f"Add story error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/progress")
async def get_progress(db: Session = Depends(get_db)):
    """Get progress of all stories."""
    stories = db.query(Story).all()
    result = []
    for story in stories:
        total = len(story.chapters)
        downloaded = sum(1 for c in story.chapters if c.status == 'downloaded')
        progress = (downloaded / total * 100) if total > 0 else 0

        result.append({
            "id": story.id,
            "title": story.title,
            "progress": round(progress, 1),
            "downloaded": downloaded,
            "total": total,
            "status": story.status
        })
    return result

@app.get("/story/{story_id}", response_class=HTMLResponse)
async def story_details(story_id: int, request: Request, db: Session = Depends(get_db)):
    """Render story details page."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    chapters = db.query(Chapter).filter(Chapter.story_id == story_id).order_by(Chapter.volume_number, Chapter.index).all()

    # Identify available volumes
    volumes = sorted(list(set(c.volume_number for c in chapters if c.volume_number is not None)))
    if not volumes and chapters:
        volumes = [1]

    return templates.TemplateResponse("story_details.html", {
        "request": request,
        "story": story,
        "chapters": chapters,
        "volumes": volumes
    })

@app.post("/api/compile/{story_id}/{volume_number}")
async def compile_volume(story_id: int, volume_number: int):
    """Compile a volume into an EPUB."""
    try:
        builder = EbookBuilder()
        output_path = builder.compile_volume(story_id, volume_number)

        if not output_path or not os.path.exists(output_path):
             raise HTTPException(status_code=500, detail="Failed to create ebook file")

        filename = os.path.basename(output_path)
        return FileResponse(output_path, media_type='application/epub+zip', filename=filename)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Compile error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
