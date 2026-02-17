import logging
import os
import psutil
import shutil
import time
from typing import Optional, List, Dict

from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from database import SessionLocal, Story, Chapter, Source, DownloadHistory, EbookProfile, NotificationSettings
from story_manager import StoryManager
from ebook_builder import EbookBuilder
from job_manager import JobManager
from notifications import NotificationManager
from config import config_manager
from logger import setup_logging

# Configure logging
setup_logging(log_level=config_manager.get('log_level'), log_file='logs/scrollarr.log')
logger = logging.getLogger(__name__)

START_TIME = time.time()

app = FastAPI(title="Scrollarr")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )

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
    profile_id: Optional[int] = None
    provider_key: Optional[str] = None

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
    library_path: str = "library"
    filename_pattern: str = "{Title} - Vol {Volume}"

class ProfileCreate(BaseModel):
    name: str
    description: Optional[str] = None
    css: Optional[str] = None
    output_format: str = 'epub'
    pdf_page_size: str = 'A4'

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    css: Optional[str] = None
    output_format: Optional[str] = None
    pdf_page_size: Optional[str] = None

class SetProfileRequest(BaseModel):
    profile_id: int

class ProfileResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    css: Optional[str] = None
    output_format: str
    pdf_page_size: Optional[str] = 'A4'

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: int
    name: str
    kind: str
    target: str
    events: str
    attach_file: bool
    enabled: bool

    class Config:
        from_attributes = True

class NotificationCreate(BaseModel):
    name: str
    kind: str
    target: str
    events: str = ''
    attach_file: bool = False
    enabled: bool = True

class NotificationUpdate(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    target: Optional[str] = None
    events: Optional[str] = None
    attach_file: Optional[bool] = None
    enabled: Optional[bool] = None

class SmtpSettingsRequest(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None

class TestNotificationRequest(BaseModel):
    target: str
    kind: str

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
        failed = sum(1 for c in story.chapters if c.status == 'failed')
        progress = (downloaded / total * 100) if total > 0 else 0

        # Add attributes for the template
        story.progress = round(progress, 1)
        story.total_chapters = total
        story.downloaded_chapters = downloaded
        story.failed_chapters = failed
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

@app.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request):
    """Render the release calendar page."""
    return templates.TemplateResponse("calendar.html", {"request": request})

@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """Render the status page."""
    return templates.TemplateResponse("status.html", {"request": request})

@app.get("/api/status")
async def get_system_status():
    """Get system status metrics."""
    try:
        # Disk Usage
        total, used, free = shutil.disk_usage("/")
        disk_usage = {
            "total": f"{total / (1024**3):.2f} GB",
            "used": f"{used / (1024**3):.2f} GB",
            "free": f"{free / (1024**3):.2f} GB",
            "percent": f"{(used / total) * 100:.1f}%"
        }

        # Database Size
        db_url = config_manager.get("database_url", "sqlite:///library.db")
        db_size = "Unknown"
        if db_url.startswith("sqlite"):
            db_path = db_url.replace("sqlite:///", "")
            if os.path.exists(db_path):
                size_bytes = os.path.getsize(db_path)
                db_size = f"{size_bytes / (1024**2):.2f} MB"

        # Memory Usage
        mem = psutil.virtual_memory()
        memory_usage = {
            "total": f"{mem.total / (1024**3):.2f} GB",
            "available": f"{mem.available / (1024**3):.2f} GB",
            "percent": f"{mem.percent}%"
        }

        # Process Memory
        process = psutil.Process()
        process_mem = process.memory_info().rss / (1024**2) # MB

        # CPU Usage
        cpu_percent = psutil.cpu_percent(interval=None)

        # Uptime
        uptime_seconds = time.time() - START_TIME
        uptime_hours = int(uptime_seconds // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        uptime = f"{uptime_hours}h {uptime_minutes}m"

        return {
            "disk": disk_usage,
            "database_size": db_size,
            "memory": memory_usage,
            "process_memory": f"{process_mem:.2f} MB",
            "cpu_percent": f"{cpu_percent}%",
            "uptime": uptime
        }
    except Exception as e:
        logger.error(f"Error fetching status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
async def get_logs(lines: int = 100):
    """Get the last N lines of logs."""
    log_file = "logs/scrollarr.log"
    try:
        if not os.path.exists(log_file):
            return {"logs": "Log file not found."}

        from collections import deque
        with open(log_file, "r") as f:
            # Efficiently read last N lines
            last_lines = deque(f, maxlen=lines)
            return {"logs": "".join(last_lines)}
    except Exception as e:
         logger.error(f"Error reading logs: {e}")
         return {"logs": f"Error reading logs: {str(e)}"}

@app.get("/api/calendar")
async def get_calendar_events(response: Response, start: Optional[str] = None, end: Optional[str] = None):
    """Get calendar events for all stories."""
    # Prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    if not story_manager:
        raise HTTPException(status_code=500, detail="StoryManager not initialized")

    try:
        events = story_manager.get_calendar_events(start, end)
        return events
    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render the settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/sources", response_class=HTMLResponse)
async def sources_page(request: Request):
    """Render the sources page."""
    return templates.TemplateResponse("sources.html", {"request": request})

@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    """Render the notifications page."""
    return templates.TemplateResponse("notifications.html", {"request": request})

@app.get("/profiles", response_class=HTMLResponse)
async def profiles_page(request: Request):
    """Render the profiles page."""
    return templates.TemplateResponse("profiles.html", {"request": request})

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Render the search page."""
    return templates.TemplateResponse("search.html", {"request": request})

@app.get("/api/search")
async def search_stories(query: str, provider: Optional[str] = None):
    """Search for stories."""
    if not story_manager:
        raise HTTPException(status_code=500, detail="StoryManager not initialized")

    try:
        results = story_manager.search(query, provider)
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sources/{source_key}/config")
async def config_source(source_key: str, config: Dict, db: Session = Depends(get_db)):
    """Update source configuration."""
    source = db.query(Source).filter(Source.key == source_key).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    try:
        # Store as JSON string
        import json
        source.config = json.dumps(config)
        db.commit()

        # Reload providers to apply new config
        if story_manager:
            story_manager.reload_providers()

        return {"message": f"Configuration for {source.name} updated"}
    except Exception as e:
        logger.error(f"Config update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        config_manager.set("library_path", settings.library_path)
        config_manager.set("filename_pattern", settings.filename_pattern)

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
        story_id = story_manager.add_story(request.url, request.profile_id, request.provider_key)
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
        failed = sum(1 for c in story.chapters if c.status == 'failed')
        progress = (downloaded / total * 100) if total > 0 else 0

        result.append({
            "id": story.id,
            "title": story.title,
            "progress": round(progress, 1),
            "downloaded": downloaded,
            "failed": failed,
            "total": total,
            "status": story.status
        })
    return result

@app.post("/api/story/{story_id}/update")
def update_story(story_id: int):
    """Force update a single story."""
    if not story_manager:
        raise HTTPException(status_code=500, detail="StoryManager not initialized")
    try:
        new_chapters = story_manager.check_story_updates(story_id)
        return {"message": f"Update complete. Found {new_chapters} new chapters.", "new_chapters": new_chapters}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/story/{story_id}/retry")
def retry_story(story_id: int):
    """Retry all failed chapters for a story."""
    if not story_manager:
        raise HTTPException(status_code=500, detail="StoryManager not initialized")
    try:
        count = story_manager.retry_failed_chapters(story_id)
        return {"message": f"Queued {count} failed chapters for retry.", "count": count}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Retry error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/story/{story_id}")
async def delete_story(story_id: int, delete_content: bool = False):
    """Delete a story."""
    if not story_manager:
        raise HTTPException(status_code=500, detail="StoryManager not initialized")
    try:
        story_manager.delete_story(story_id, delete_content)
        return {"message": "Story deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/story/{story_id}/toggle-notifications")
async def toggle_story_notifications(story_id: int, db: Session = Depends(get_db)):
    """Toggle notification settings for a story."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    story.notify_on_new_chapter = not story.notify_on_new_chapter
    db.commit()
    return {"message": "Notifications updated", "notify_on_new_chapter": story.notify_on_new_chapter}

@app.get("/story/{story_id}", response_class=HTMLResponse)
async def story_details(story_id: int, request: Request, db: Session = Depends(get_db)):
    """Render story details page."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    chapters = db.query(Chapter).filter(Chapter.story_id == story_id).order_by(Chapter.volume_number, Chapter.index).all()

    # Identify available volumes
    volume_numbers = sorted(list(set(c.volume_number for c in chapters if c.volume_number is not None)))
    if not volume_numbers and chapters:
        volume_numbers = [1]

    # Group chapters by volume
    grouped_volumes = {}
    for chapter in chapters:
        v_num = chapter.volume_number if chapter.volume_number is not None else 1
        if v_num not in grouped_volumes:
            grouped_volumes[v_num] = {
                'number': v_num,
                'title': chapter.volume_title or f"Volume {v_num}",
                'chapters': []
            }
        # Update title if it was missing but found later (though usually consistent within volume)
        if not grouped_volumes[v_num]['title'] or grouped_volumes[v_num]['title'].startswith("Volume "):
             if chapter.volume_title:
                 grouped_volumes[v_num]['title'] = chapter.volume_title

        grouped_volumes[v_num]['chapters'].append(chapter)

    # Sort volumes
    volumes = sorted(grouped_volumes.values(), key=lambda x: x['number'])

    # Sort chapters within volumes
    for vol in volumes:
        vol['chapters'].sort(key=lambda c: c.index if c.index is not None else 0)

    stats = {
        'total_volumes': len(volumes),
        'total_chapters': len(chapters),
        'downloaded_chapters': sum(1 for c in chapters if c.status == 'downloaded'),
        'failed_chapters': sum(1 for c in chapters if c.status == 'failed')
    }

    # Get all profiles
    profiles = db.query(EbookProfile).all()

    return templates.TemplateResponse("story_details.html", {
        "request": request,
        "story": story,
        "chapters": chapters,
        "volumes": volumes,
        "stats": stats,
        "profiles": profiles
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

@app.get("/api/profiles", response_model=List[ProfileResponse])
async def get_profiles(db: Session = Depends(get_db)):
    """Get all profiles."""
    profiles = db.query(EbookProfile).all()
    return profiles

@app.post("/api/profiles", response_model=ProfileResponse)
async def create_profile(profile: ProfileCreate, db: Session = Depends(get_db)):
    """Create a new profile."""
    # Check if name exists
    existing = db.query(EbookProfile).filter(EbookProfile.name == profile.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile with this name already exists")

    new_profile = EbookProfile(
        name=profile.name,
        description=profile.description,
        css=profile.css,
        output_format=profile.output_format,
        pdf_page_size=profile.pdf_page_size
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile

@app.put("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(profile_id: int, profile: ProfileUpdate, db: Session = Depends(get_db)):
    """Update a profile."""
    db_profile = db.query(EbookProfile).filter(EbookProfile.id == profile_id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if profile.name:
        # Check uniqueness if name changed
        if profile.name != db_profile.name:
             existing = db.query(EbookProfile).filter(EbookProfile.name == profile.name).first()
             if existing:
                 raise HTTPException(status_code=400, detail="Profile with this name already exists")
        db_profile.name = profile.name

    if profile.description is not None:
        db_profile.description = profile.description
    if profile.css is not None:
        db_profile.css = profile.css
    if profile.output_format is not None:
        db_profile.output_format = profile.output_format
    if profile.pdf_page_size is not None:
        db_profile.pdf_page_size = profile.pdf_page_size

    db.commit()
    return db_profile

@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    """Delete a profile."""
    # Prevent deleting default profile (id=1)
    if profile_id == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the default profile")

    db_profile = db.query(EbookProfile).filter(EbookProfile.id == profile_id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Check if used by stories
    used_count = db.query(Story).filter(Story.profile_id == profile_id).count()
    if used_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete profile because it is used by {used_count} stories")

    db.delete(db_profile)
    db.commit()
    return {"message": "Profile deleted"}

@app.post("/api/story/{story_id}/set_profile")
async def set_story_profile(story_id: int, request: SetProfileRequest, db: Session = Depends(get_db)):
    """Assign a profile to a story."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    profile = db.query(EbookProfile).filter(EbookProfile.id == request.profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    story.profile_id = request.profile_id
    db.commit()
    return {"message": f"Profile set to {profile.name}"}

# Notification API Endpoints

@app.get("/api/notifications/settings")
async def get_notification_settings(db: Session = Depends(get_db)):
    """Get all notification settings and SMTP config."""
    targets = db.query(NotificationSettings).all()

    smtp_config = {
        "smtp_host": config_manager.get("smtp_host", ""),
        "smtp_port": int(config_manager.get("smtp_port", 587)),
        "smtp_user": config_manager.get("smtp_user", ""),
        "smtp_password": config_manager.get("smtp_password", ""),
        "smtp_from_email": config_manager.get("smtp_from_email", "")
    }

    return {
        "targets": [NotificationResponse.model_validate(t) for t in targets],
        "smtp": smtp_config
    }

@app.post("/api/notifications/smtp")
async def update_smtp_settings(settings: SmtpSettingsRequest):
    """Update SMTP configuration."""
    try:
        config_manager.set("smtp_host", settings.smtp_host)
        config_manager.set("smtp_port", settings.smtp_port)
        config_manager.set("smtp_user", settings.smtp_user)
        config_manager.set("smtp_password", settings.smtp_password)
        config_manager.set("smtp_from_email", settings.smtp_from_email)
        return {"message": "SMTP settings updated"}
    except Exception as e:
        logger.error(f"Error updating SMTP settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update SMTP settings")

@app.post("/api/notifications/targets", response_model=NotificationResponse)
async def create_notification_target(target: NotificationCreate, db: Session = Depends(get_db)):
    """Create a new notification target."""
    new_target = NotificationSettings(
        name=target.name,
        kind=target.kind,
        target=target.target,
        events=target.events,
        attach_file=target.attach_file,
        enabled=target.enabled
    )
    db.add(new_target)
    db.commit()
    db.refresh(new_target)
    return new_target

@app.put("/api/notifications/targets/{target_id}", response_model=NotificationResponse)
async def update_notification_target(target_id: int, target: NotificationUpdate, db: Session = Depends(get_db)):
    """Update a notification target."""
    db_target = db.query(NotificationSettings).filter(NotificationSettings.id == target_id).first()
    if not db_target:
        raise HTTPException(status_code=404, detail="Target not found")

    if target.name is not None:
        db_target.name = target.name
    if target.kind is not None:
        db_target.kind = target.kind
    if target.target is not None:
        db_target.target = target.target
    if target.events is not None:
        db_target.events = target.events
    if target.attach_file is not None:
        db_target.attach_file = target.attach_file
    if target.enabled is not None:
        db_target.enabled = target.enabled

    db.commit()
    return db_target

@app.delete("/api/notifications/targets/{target_id}")
async def delete_notification_target(target_id: int, db: Session = Depends(get_db)):
    """Delete a notification target."""
    db_target = db.query(NotificationSettings).filter(NotificationSettings.id == target_id).first()
    if not db_target:
        raise HTTPException(status_code=404, detail="Target not found")

    db.delete(db_target)
    db.commit()
    return {"message": "Target deleted"}

@app.post("/api/notifications/test")
async def test_notification(request: TestNotificationRequest):
    """Send a test notification."""
    nm = NotificationManager()
    try:
        if request.kind == 'email':
            nm.send_email(request.target, "Scrollarr Test", "This is a test notification from Scrollarr.")
        elif request.kind == 'webhook':
            nm.send_webhook(request.target, "This is a test notification from Scrollarr.", {"source": "test"})
        else:
            raise HTTPException(status_code=400, detail="Invalid kind")

        return {"message": "Test notification sent"}
    except Exception as e:
        logger.error(f"Test notification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
