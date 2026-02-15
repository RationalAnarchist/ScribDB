import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, text, DateTime
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from sqlalchemy.sql import func
from typing import Optional
from core_logic import SourceManager
from royalroad import RoyalRoadSource
from config import config_manager

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

def init_db(engine=engine):
    """Creates the database tables and runs migrations."""
    Base.metadata.create_all(bind=engine)
    migrate_db(engine)

def migrate_db(engine):
    """
    Checks for missing columns and adds them if necessary.
    Specifically checks for 'monitored' in 'stories' table.
    """
    with engine.connect() as conn:
        # Check for monitored column in stories
        # SQLite specific check
        try:
            result = conn.execute(text("PRAGMA table_info(stories)"))
            columns = [row[1] for row in result.fetchall()]
            if 'monitored' not in columns:
                conn.execute(text("ALTER TABLE stories ADD COLUMN monitored BOOLEAN DEFAULT 1"))
            if 'last_updated' not in columns:
                conn.execute(text("ALTER TABLE stories ADD COLUMN last_updated DATETIME"))
            if 'status' not in columns:
                conn.execute(text("ALTER TABLE stories ADD COLUMN status VARCHAR DEFAULT 'Monitoring'"))
            if 'is_monitored' not in columns:
                conn.execute(text("ALTER TABLE stories ADD COLUMN is_monitored BOOLEAN DEFAULT 1"))
                conn.execute(text("UPDATE stories SET is_monitored = monitored WHERE is_monitored IS NULL"))
            if 'last_checked' not in columns:
                conn.execute(text("ALTER TABLE stories ADD COLUMN last_checked DATETIME"))
        except Exception as e:
            print(f"Migration error (stories): {e}")

        try:
            result = conn.execute(text("PRAGMA table_info(chapters)"))
            columns = [row[1] for row in result.fetchall()]
            if 'volume_number' not in columns:
                conn.execute(text("ALTER TABLE chapters ADD COLUMN volume_number INTEGER DEFAULT 1"))
                conn.execute(text("UPDATE chapters SET volume_number = 1 WHERE volume_number IS NULL"))
            if 'index' not in columns:
                conn.execute(text("ALTER TABLE chapters ADD COLUMN 'index' INTEGER"))
            if 'status' not in columns:
                conn.execute(text("ALTER TABLE chapters ADD COLUMN status VARCHAR DEFAULT 'pending'"))
                conn.execute(text("UPDATE chapters SET status = 'downloaded' WHERE is_downloaded = 1"))
                conn.execute(text("UPDATE chapters SET status = 'pending' WHERE is_downloaded = 0 OR is_downloaded IS NULL"))
        except Exception as e:
            print(f"Migration error (chapters): {e}")

        # Check for sources population
        try:
            result = conn.execute(text("SELECT count(*) FROM sources"))
            count = result.scalar()
            if count == 0:
                 conn.execute(text("INSERT INTO sources (name, key, is_enabled) VALUES ('Royal Road', 'royalroad', 1)"))
                 conn.execute(text("INSERT INTO sources (name, key, is_enabled) VALUES ('Archive of Our Own', 'ao3', 1)"))
                 conn.commit()
        except Exception as e:
            print(f"Migration error (sources population): {e}")

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
