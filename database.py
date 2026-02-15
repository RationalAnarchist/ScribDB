import os
import sys
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, text, DateTime, inspect
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from sqlalchemy.sql import func
from typing import Optional
from core_logic import SourceManager
from royalroad import RoyalRoadSource
from config import config_manager
import alembic.config
import alembic.command

Base = declarative_base()

class Story(Base):
    __tablename__ = 'stories'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=False)
    source_url = Column(String, unique=True, nullable=False)
    cover_path = Column(String, nullable=True)
    monitored = Column(Boolean, default=True)
    is_monitored = Column(Boolean, default=True)
    last_updated = Column(DateTime, nullable=True)
    last_checked = Column(DateTime, nullable=True)
    status = Column(String, default='Monitoring')

    chapters = relationship("Chapter", back_populates="story", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Story(title='{self.title}', author='{self.author}')>"

class Chapter(Base):
    __tablename__ = 'chapters'

    id = Column(Integer, primary_key=True)
    story_id = Column(Integer, ForeignKey('stories.id'), nullable=False)
    title = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    local_path = Column(String, nullable=True)
    is_downloaded = Column(Boolean, default=False)
    volume_number = Column(Integer, default=1)
    index = Column(Integer, nullable=True)
    status = Column(String, default='pending')

    story = relationship("Story", back_populates="chapters")

    def __repr__(self):
        return f"<Chapter(title='{self.title}', story_id={self.story_id})>"

class DownloadHistory(Base):
    __tablename__ = 'download_history'

    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False)
    story_id = Column(Integer, ForeignKey('stories.id'), nullable=False)
    status = Column(String, nullable=False)  # 'downloaded', 'failed'
    timestamp = Column(DateTime, server_default=func.now())
    details = Column(String, nullable=True)

    chapter = relationship("Chapter")
    story = relationship("Story")

    def __repr__(self):
        return f"<DownloadHistory(chapter_id={self.chapter_id}, status='{self.status}')>"

class Source(Base):
    __tablename__ = 'sources'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    key = Column(String, unique=True, nullable=False)
    is_enabled = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Source(name='{self.name}', enabled={self.is_enabled})>"

# Setup database
# Priority: Environment Variable > Config file > Default
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    DB_URL = config_manager.get("database_url", "sqlite:///library.db")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_migrations():
    """Run Alembic migrations programmatically."""
    print("Checking for database migrations...")

    # Locate alembic.ini
    alembic_ini_path = os.path.join(os.getcwd(), "alembic.ini")
    if not os.path.exists(alembic_ini_path):
        print(f"Warning: alembic.ini not found at {alembic_ini_path}. Skipping migrations.")
        return

    alembic_cfg = alembic.config.Config(alembic_ini_path)

    # Check if tables exist but no alembic_version (existing non-alembic DB)
    inspector = inspect(engine)
    try:
        tables = inspector.get_table_names()
    except Exception:
        # DB might not exist yet
        tables = []

    if "stories" in tables and "alembic_version" not in tables:
        print("Existing database detected without alembic version. Stamping head.")
        try:
            alembic.command.stamp(alembic_cfg, "head")
        except Exception as e:
            print(f"Error stamping database: {e}")
            # If stamp fails, we might be in trouble, but let's try to proceed

    print("Running alembic upgrade head...")
    try:
        alembic.command.upgrade(alembic_cfg, "head")
        print("Migrations completed.")
    except Exception as e:
        print(f"Error running migrations: {e}")
        raise e

def init_db(engine=engine):
    """Creates the database tables and runs migrations."""
    # We now rely on Alembic to create tables and manage schema
    run_migrations()

def sync_story(url: str, session: Optional[Session] = None):
    """
    Fetches the latest chapters for the story at the given URL and updates the database.
    """
    # 1. Setup SourceManager
    manager = SourceManager()
    manager.register_provider(RoyalRoadSource())

    # 2. Get Provider
    provider = manager.get_provider_for_url(url)
    if not provider:
        raise ValueError(f"No provider found for URL: {url}")

    # 3. Fetch Data
    metadata = provider.get_metadata(url)
    chapters_data = provider.get_chapter_list(url)

    # 4. Update Database
    should_close = False
    if session is None:
        session = SessionLocal()
        should_close = True

    try:
        # Check if story exists
        story = session.query(Story).filter(Story.source_url == url).first()

        if not story:
            story = Story(
                title=metadata.get('title', 'Unknown'),
                author=metadata.get('author', 'Unknown'),
                source_url=url,
                cover_path=None,
                status='Monitoring'
            )
            session.add(story)
            session.flush() # Ensure ID is available
        else:
            # Update metadata if needed
            story.title = metadata.get('title', story.title)
            story.author = metadata.get('author', story.author)

        # If story is new, story.chapters is empty.
        # If story exists, story.chapters contains current DB chapters.
        existing_chapters = {}
        if story.chapters:
             existing_chapters = {c.source_url: c for c in story.chapters}

        new_chapters_count = 0
        for i, chapter_data in enumerate(chapters_data):
            chapter_url = chapter_data['url']
            chapter_title = chapter_data['title']

            if chapter_url not in existing_chapters:
                new_chapter = Chapter(
                    title=chapter_title,
                    source_url=chapter_url,
                    index=i + 1
                )
                # Associate with story
                story.chapters.append(new_chapter)
                new_chapters_count += 1
            else:
                # Update index if it's missing or changed
                existing_chap = existing_chapters[chapter_url]
                if existing_chap.index != i + 1:
                    existing_chap.index = i + 1

        if new_chapters_count > 0:
            story.last_updated = func.now()

        session.commit()

    except Exception as e:
        session.rollback()
        raise e
    finally:
        if should_close:
            session.close()

if __name__ == "__main__":
    init_db()
