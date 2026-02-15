import os
import logging
from typing import Optional
from sqlalchemy.orm import Session
from core_logic import SourceManager
from royalroad import RoyalRoadSource
from database import Story, Chapter, SessionLocal, init_db, engine

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
        self.source_manager.register_provider(RoyalRoadSource())
        logger.info("StoryManager initialized and providers registered.")

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
                    cover_path=metadata.get('cover_url')
                )
                session.add(story)
                session.flush()
            else:
                logger.info("Updating existing story record.")
                story.title = metadata.get('title', story.title)
                story.author = metadata.get('author', story.author)
                # cover might be updated too if needed

            # Handle chapters
            existing_urls = {c.source_url for c in story.chapters}
            new_chapters_count = 0

            for chapter_data in chapters_data:
                c_url = chapter_data['url']
                if c_url not in existing_urls:
                    new_chapter = Chapter(
                        title=chapter_data['title'],
                        source_url=c_url,
                        story_id=story.id
                    )
                    session.add(new_chapter)
                    new_chapters_count += 1

            session.commit()
            logger.info(f"Story '{story.title}' processed. Added {new_chapters_count} new chapters.")
            return story.id

        except Exception as e:
            session.rollback()
            logger.error(f"Error adding story: {e}")
            raise e
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
            story_dir = os.path.join("saved_stories", f"{story_id}_{safe_title.replace(' ', '_')}")
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
                    session.commit() # Commit after each chapter to save progress

                except Exception as e:
                    logger.error(f"Failed to download chapter {chapter.title}: {e}")
                    # Optionally continue to next chapter or break
        finally:
            session.close()
