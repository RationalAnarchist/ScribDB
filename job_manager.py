import logging
import time
import os
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func
from database import SessionLocal, Story, Chapter, init_db
from story_manager import StoryManager
from config import config_manager

# Configure logging
logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.story_manager = StoryManager()

    def start(self):
        """Starts the scheduler with configured jobs."""
        init_db()
        self.update_jobs()
        self.scheduler.start()
        logger.info("JobManager started.")

    def stop(self):
        """Stops the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("JobManager stopped.")

    def update_jobs(self):
        """Updates or adds jobs based on current configuration."""
        # Update Job
        update_interval = config_manager.get("update_interval_hours", 1)
        # APScheduler handles replace_existing=True gracefully
        self.scheduler.add_job(
            self.check_for_updates,
            'interval',
            hours=update_interval,
            id='check_updates',
            replace_existing=True
        )

        # Download Job
        # worker.py slept random(min, max). We'll use min as the base interval.
        download_interval = config_manager.get("worker_sleep_min", 30.0)

        self.scheduler.add_job(
            self.process_download_queue,
            'interval',
            seconds=download_interval,
            id='download_queue',
            max_instances=1, # Prevent overlap
            replace_existing=True
        )
        logger.info(f"Jobs updated: check_updates (every {update_interval}h), download_queue (every {download_interval}s)")

    def check_for_updates(self):
        """
        Checks for updates for all monitored stories.
        Fetches the latest chapter list and adds new chapters to the database.
        """
        logger.info("Checking for updates...")
        session = SessionLocal()

        try:
            monitored_stories = session.query(Story).filter(Story.is_monitored == True).all()

            for story in monitored_stories:
                logger.info(f"Checking '{story.title}'...")
                try:
                    provider = self.story_manager.source_manager.get_provider_for_url(story.source_url)
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

    def process_download_queue(self):
        """
        Downloads one pending chapter.
        """
        session = SessionLocal()

        try:
            # Query the database for the single oldest chapter where status == 'pending'
            # Use with_for_update() to lock the row if possible
            chapter = session.query(Chapter).filter(Chapter.status == 'pending').order_by(Chapter.id.asc()).with_for_update().first()

            if chapter:
                story = chapter.story
                logger.info(f"Processing chapter: {chapter.title} (ID: {chapter.id}) from story: {story.title}")

                try:
                    # The Download: Use the provider to get the content.
                    provider = self.story_manager.source_manager.get_provider_for_url(story.source_url)
                    if not provider:
                         raise ValueError(f"No provider found for story URL: {story.source_url}")

                    content = provider.get_chapter_content(chapter.source_url)

                    # Create safe directory name
                    safe_story_title = "".join([c for c in story.title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(' ', '_')
                    story_dir = os.path.join(config_manager.get('download_path'), f"{story.id}_{safe_story_title}")
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
                # No pending chapters, just return silently or debug log
                pass

        except Exception as e:
            logger.error(f"Worker error: {e}")
            session.rollback()
        finally:
            session.close()
