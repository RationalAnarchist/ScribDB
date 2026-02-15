import os
import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func
from database import SessionLocal, Story, Chapter, init_db
from story_manager import StoryManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_for_updates():
    """
    Checks for updates for all monitored stories.
    Fetches the latest chapter list and adds new chapters to the database.
    """
    logger.info("Checking for updates...")
    session = SessionLocal()
    story_manager = StoryManager()

    try:
        monitored_stories = session.query(Story).filter(Story.is_monitored == True).all()

        for story in monitored_stories:
            logger.info(f"Checking '{story.title}'...")
            try:
                provider = story_manager.source_manager.get_provider_for_url(story.source_url)
                if not provider:
                    logger.warning(f"No provider found for: {story.title}")
                    continue

                remote_chapters = provider.get_chapter_list(story.source_url)

                # Get existing chapters from DB
                existing_urls = {c.source_url for c in story.chapters}

                new_chapters_count = 0
                for i, chapter_data in enumerate(remote_chapters):
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

                story.last_checked = func.now()
                if new_chapters_count > 0:
                    story.last_updated = func.now()
                    logger.info(f"Found {new_chapters_count} new chapters for '{story.title}'.")

                session.commit()

            except Exception as e:
                logger.error(f"Error checking updates for '{story.title}': {e}")
                session.rollback()

    except Exception as e:
        logger.error(f"Error during update check: {e}")
    finally:
        session.close()

def process_download_queue():
    """
    Downloads one pending chapter.
    """
    logger.info("Processing download queue...")
    session = SessionLocal()
    story_manager = StoryManager()

    try:
        # Get one pending chapter
        chapter = session.query(Chapter).filter(Chapter.status == 'pending').first()

        if not chapter:
            logger.info("No pending chapters.")
            return

        story = chapter.story
        logger.info(f"Downloading chapter: {chapter.title} for story: {story.title}")

        try:
            provider = story_manager.source_manager.get_provider_for_url(story.source_url)
            if not provider:
                raise ValueError(f"No provider found for story URL: {story.source_url}")

            content = provider.get_chapter_content(chapter.source_url)

            # Create safe directory name
            safe_story_title = "".join([c for c in story.title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(' ', '_')
            story_dir = os.path.join("saved_stories", f"{story.id}_{safe_story_title}")
            os.makedirs(story_dir, exist_ok=True)

            # Create safe filename
            safe_chapter_title = "".join([c for c in chapter.title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(' ', '_')
            filename = f"{chapter.id}_{safe_chapter_title}.html"
            filepath = os.path.join(story_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            chapter.local_path = filepath
            chapter.is_downloaded = True
            chapter.status = 'downloaded'
            session.commit()
            logger.info(f"Successfully downloaded: {chapter.title}")

        except Exception as e:
            logger.error(f"Failed to download chapter {chapter.title}: {e}")
            chapter.status = 'failed'
            session.commit()

    except Exception as e:
        logger.error(f"Error processing download queue: {e}")
    finally:
        session.close()

def start_scheduler():
    """
    Starts the background scheduler.
    """
    init_db()

    scheduler = BackgroundScheduler()

    # Check for updates every hour
    scheduler.add_job(check_for_updates, 'interval', hours=1)

    # Process download queue every 2 minutes
    scheduler.add_job(process_download_queue, 'interval', minutes=2)

    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to exit.")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping scheduler...")
        scheduler.shutdown()

if __name__ == "__main__":
    start_scheduler()
