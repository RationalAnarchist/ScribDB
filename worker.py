import os
import time
import random
import logging
from database import SessionLocal, Chapter, Story, init_db
from royalroad import RoyalRoadSource

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def worker():
    """
    Single-worker queue to download chapters.
    """
    logger.info("Worker started...")

    # Ensure database is initialized
    init_db()

    while True:
        # Random sleep time between 30 and 60 seconds
        sleep_time = random.uniform(30, 60)

        session = SessionLocal()
        try:
            # Query the database for the single oldest chapter where status == 'pending'
            # Use with_for_update() to lock the row if possible (mostly for databases that support it like Postgres)
            chapter = session.query(Chapter).filter(Chapter.status == 'pending').order_by(Chapter.id.asc()).with_for_update().first()

            if chapter:
                # The In-Memory Lock: We hold the chapter object in memory.
                # Since we are inside a transaction (session), and used with_for_update,
                # this should prevent other workers (if any) from picking it up in supported DBs.

                story = chapter.story
                logger.info(f"Processing chapter: {chapter.title} (ID: {chapter.id}) from story: {story.title}")

                try:
                    # The Download: Use the RoyalRoadSource to get the content.
                    provider = RoyalRoadSource()
                    content = provider.get_chapter_content(chapter.source_url)

                    # Create safe directory name
                    # logic from scheduler.py
                    safe_story_title = "".join([c for c in story.title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(' ', '_')
                    story_dir = os.path.join("saved_stories", f"{story.id}_{safe_story_title}")
                    os.makedirs(story_dir, exist_ok=True)

                    # Create safe filename
                    safe_chapter_title = "".join([c for c in chapter.title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(' ', '_')
                    filename = f"{chapter.id}_{safe_chapter_title}.html"
                    filepath = os.path.join(story_dir, filename)

                    # Write file to disk
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                    # The Update: Once the file is written to disk, update the status from pending to downloaded.
                    chapter.local_path = filepath
                    chapter.is_downloaded = True
                    chapter.status = 'downloaded'
                    session.commit()
                    logger.info(f"Successfully downloaded: {chapter.title}")

                except Exception as e:
                    logger.error(f"Failed to download chapter {chapter.title}: {e}")
                    # Error Handling: If the download fails, change the status to failed so we can track it.
                    chapter.status = 'failed'
                    session.commit()

            else:
                logger.info("No pending chapters.")

        except Exception as e:
            logger.error(f"Worker error: {e}")
            session.rollback()
        finally:
            session.close()

        logger.info(f"Sleeping for {sleep_time:.2f} seconds...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    worker()
