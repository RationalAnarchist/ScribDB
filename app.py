import threading
import logging
import os
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import SessionLocal, Story, Chapter
from story_manager import StoryManager
from worker import worker
from ebook_builder import EbookBuilder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

@app.on_event("startup")
async def startup_event():
    """Start the background worker thread."""
    logger.info("Starting worker thread...")
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    logger.info("Worker thread started.")

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
