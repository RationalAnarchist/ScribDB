import os
import logging
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func
from core_logic import SourceManager
from royalroad import RoyalRoadSource
from ao3 import AO3Source
from database import Story, Chapter, Source, SessionLocal, init_db, engine
from config import config_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StoryManager:
    def __init__(self):
        """
        Initializes the StoryManager.
        Ensures the database is ready and registers providers.
        """
        # Ensure database tables exist
        init_db()

        self.source_manager = SourceManager()
        self.reload_providers()
        logger.info("StoryManager initialized and providers registered.")

    def reload_providers(self):
        """
        Reloads providers based on enabled sources in the database.
        """
        self.source_manager.clear_providers()
        session = SessionLocal()
        try:
            enabled_sources = session.query(Source).filter(Source.is_enabled == True).all()
            enabled_keys = {s.key for s in enabled_sources}

            # Map keys to provider classes
            providers_map = {
                'royalroad': RoyalRoadSource,
                'ao3': AO3Source
            }

            registered_count = 0
            for key, provider_class in providers_map.items():
                if key in enabled_keys:
                    self.source_manager.register_provider(provider_class())
                    registered_count += 1

            logger.info(f"Reloaded providers. {registered_count} providers active.")
        except Exception as e:
            logger.error(f"Error reloading providers: {e}")
        finally:
            session.close()

    def add_story(self, url: str) -> int:
        """
        Adds a story to the database from the given URL.
        Fetches metadata and chapter list.
        Returns the story ID.
        """
        logger.info(f"Adding story from URL: {url}")

        provider = self.source_manager.get_provider_for_url(url)
        if not provider:
            raise ValueError(f"No provider found for URL: {url}")

        metadata = provider.get_metadata(url)
        chapters_data = provider.get_chapter_list(url)

        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.source_url == url).first()

            if not story:
                logger.info("Creating new story record.")
                story = Story(
                    title=metadata.get('title', 'Unknown'),
                    author=metadata.get('author', 'Unknown'),
                    source_url=url,
                    cover_path=metadata.get('cover_url'),
                    status='Monitoring'
                )
                session.add(story)
                session.flush()
            else:
                logger.info("Updating existing story record.")
                story.title = metadata.get('title', story.title)
                story.author = metadata.get('author', story.author)
                # cover might be updated too if needed

            # Handle chapters
            existing_urls = {c.source_url: c for c in story.chapters}
            new_chapters_count = 0

            for i, chapter_data in enumerate(chapters_data):
                c_url = chapter_data['url']
                if c_url not in existing_urls:
                    new_chapter = Chapter(
                        title=chapter_data['title'],
                        source_url=c_url,
                        story_id=story.id,
                        index=i + 1,
                        status='pending'
                    )
                    session.add(new_chapter)
                    new_chapters_count += 1
                else:
                    # Update index if needed
                    existing_chap = existing_urls[c_url]
                    if existing_chap.index != i + 1:
                        existing_chap.index = i + 1

            story.last_checked = func.now()
            if new_chapters_count > 0:
                story.last_updated = func.now()

            session.commit()
            logger.info(f"Story '{story.title}' processed. Added {new_chapters_count} new chapters.")
            return story.id

        except Exception as e:
            session.rollback()
            logger.error(f"Error adding story: {e}")
            raise e
        finally:
            session.close()

    def get_pending_chapters(self):
        """
        Returns all chapters marked as 'pending' across all monitored stories.
        """
        session = SessionLocal()
        try:
            chapters = session.query(Chapter).join(Story).options(joinedload(Chapter.story)).filter(
                Story.is_monitored == True,
                Chapter.status == 'pending'
            ).all()
            session.expunge_all()
            return chapters
        finally:
            session.close()

    def list_stories(self):
        """
        Lists all stories in the database with their download progress.
        Returns a list of dictionaries.
        """
        session = SessionLocal()
        try:
            stories = session.query(Story).all()
            result = []
            for story in stories:
                total = len(story.chapters)
                downloaded = sum(1 for c in story.chapters if c.is_downloaded)
                result.append({
                    'id': story.id,
                    'title': story.title,
                    'author': story.author,
                    'downloaded': downloaded,
                    'total': total
                })
            return result
        finally:
            session.close()

    def compile_story(self, story_id: int):
        """
        Compiles the story into an EPUB file.
        Returns the path of the generated EPUB.
        """
        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.id == story_id).first()
            if not story:
                raise ValueError(f"Story with ID {story_id} not found")

            chapters = session.query(Chapter).filter(Chapter.story_id == story_id).order_by(Chapter.id).all()

            chapter_data = []
            for chapter in chapters:
                if chapter.is_downloaded and chapter.local_path and os.path.exists(chapter.local_path):
                    with open(chapter.local_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    chapter_data.append({'title': chapter.title, 'content': content})
                else:
                    logger.warning(f"Chapter {chapter.title} (ID: {chapter.id}) is missing or not downloaded.")

            if not chapter_data:
                raise ValueError("No downloaded chapters found for this story.")

            from ebook_builder import EbookBuilder
            builder = EbookBuilder()

            safe_title = "".join([c for c in story.title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(' ', '_')
            if not safe_title:
                safe_title = f"story_{story_id}"

            output_path = f"{safe_title}.epub"

            builder.make_epub(story.title, story.author, chapter_data, output_path, story.cover_path)
            return output_path
        finally:
            session.close()

    def update_library(self):
        """
        Iterates through all stories in the database.
        For each story, fetches the current list of chapters from the web.
        Compares the web list to the database list.
        Creates a new Chapter record with status='pending' for any URL that does not exist in the database.
        """
        logger.info("Starting library update...")
        session = SessionLocal()
        try:
            # Iterate through all stories
            stories = session.query(Story).all()

            for story in stories:
                try:
                    logger.info(f"Checking updates for story: {story.title}")

                    provider = self.source_manager.get_provider_for_url(story.source_url)
                    if not provider:
                        logger.warning(f"No provider found for story: {story.title} ({story.source_url})")
                        continue

                    # Fetch current chapters from source
                    remote_chapters = provider.get_chapter_list(story.source_url)

                    # Get existing chapters from DB
                    existing_chapter_urls = {c.source_url for c in story.chapters}

                    new_chapters_count = 0
                    for i, chap_data in enumerate(remote_chapters):
                        if chap_data['url'] not in existing_chapter_urls:
                            new_chapter = Chapter(
                                title=chap_data['title'],
                                source_url=chap_data['url'],
                                story_id=story.id,
                                index=i + 1,
                                status='pending'
                            )
                            session.add(new_chapter)
                            new_chapters_count += 1

                    story.last_checked = func.now()
                    if new_chapters_count > 0:
                        story.last_updated = func.now()
                        logger.info(f"Found {new_chapters_count} new chapters for '{story.title}'")
                    else:
                        logger.info(f"No new chapters for '{story.title}'")

                    session.commit()

                except Exception as e:
                    logger.error(f"Error updating story '{story.title}': {e}")
                    session.rollback()

            logger.info("Library update completed.")

        except Exception as e:
            logger.error(f"Critical error during library update: {e}")
        finally:
            session.close()

    def download_missing_chapters(self, story_id: int):
        """
        Downloads content for all chapters of the story that are not yet downloaded.
        """
        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.id == story_id).first()
            if not story:
                raise ValueError(f"Story with ID {story_id} not found.")

            logger.info(f"Checking missing chapters for '{story.title}'...")

            # Get provider again
            provider = self.source_manager.get_provider_for_url(story.source_url)
            if not provider:
                 raise ValueError(f"Provider not found for story URL: {story.source_url}")

            missing_chapters = session.query(Chapter).filter(
                Chapter.story_id == story_id,
                Chapter.is_downloaded == False
            ).all()

            if not missing_chapters:
                logger.info("No missing chapters to download.")
                return

            logger.info(f"Found {len(missing_chapters)} chapters to download.")

            # Ensure directory exists
            # Create a safe directory name from title
            safe_title = "".join([c for c in story.title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            story_dir = os.path.join(config_manager.get('download_path'), f"{story_id}_{safe_title.replace(' ', '_')}")
            os.makedirs(story_dir, exist_ok=True)

            for chapter in missing_chapters:
                logger.info(f"Downloading chapter: {chapter.title}")
                try:
                    content = provider.get_chapter_content(chapter.source_url)

                    # Create filename
                    safe_chapter_title = "".join([c for c in chapter.title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                    filename = f"{chapter.id}_{safe_chapter_title.replace(' ', '_')}.html"
                    filepath = os.path.join(story_dir, filename)

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                    chapter.local_path = filepath
                    chapter.is_downloaded = True
                    chapter.status = 'downloaded'
                    session.commit() # Commit after each chapter to save progress

                except Exception as e:
                    logger.error(f"Failed to download chapter {chapter.title}: {e}")
                    chapter.status = 'failed'
                    session.commit()
                    # Optionally continue to next chapter or break
        finally:
            session.close()
