import logging
import time
import os
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func
from database import SessionLocal, Story, Chapter, DownloadHistory, init_db
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

        # Schedule immediate run of metadata check on startup
        from datetime import datetime, timedelta
        self.scheduler.add_job(
            self.check_missing_metadata,
            'date',
            run_date=datetime.now() + timedelta(seconds=10),
            id='check_metadata_startup'
        )

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

        # Metadata Check Job
        # Run infrequently, e.g., every 12 hours
        self.scheduler.add_job(
            self.check_missing_metadata,
            'interval',
            hours=12,
            id='check_metadata',
            replace_existing=True
        )

        logger.info(f"Jobs updated: check_updates (every {update_interval}h), download_queue (every {download_interval}s), check_metadata (every 12h)")
        for job in self.scheduler.get_jobs():
            logger.info(f"Scheduled job: {job}")

    def check_missing_metadata(self):
        """
        Checks for missing metadata in stories and attempts to retrieve it.
        """
        logger.info("Running scheduled metadata check...")
        self.story_manager.fill_missing_metadata()

    def check_for_updates(self):
        """
        Checks for updates for all monitored stories.
        Fetches the latest chapter list and adds new chapters to the database.
        """
        logger.info("Checking for updates...")
        session = SessionLocal()

        try:
            # Only get IDs to close session early and avoid holding it during network requests
            monitored_story_ids = [s.id for s in session.query(Story).filter(Story.is_monitored == True).all()]
        except Exception as e:
            logger.error(f"Error fetching monitored stories: {e}")
            monitored_story_ids = []
        finally:
            session.close()

        for story_id in monitored_story_ids:
            try:
                self.story_manager.check_story_updates(story_id)
            except Exception as e:
                logger.error(f"Error updating story {story_id}: {e}")

    def process_download_queue(self):
        """
        Downloads pending chapters until queue is empty.
        """
        logger.info("Checking download queue for pending chapters...")

        while True:
            session = SessionLocal()
            try:
                # Query the database for the single oldest chapter where status == 'pending'
                # Use with_for_update() to lock the row if possible
                chapter = session.query(Chapter).filter(Chapter.status == 'pending').order_by(Chapter.id.asc()).with_for_update().first()

                if not chapter:
                    # No more chapters
                    logger.debug("No pending chapters found.")
                    break

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

                    history = DownloadHistory(
                        chapter_id=chapter.id,
                        story_id=story.id,
                        status='downloaded',
                        details=f"Downloaded successfully to {filename}"
                    )
                    session.add(history)

                    session.commit()
                    logger.info(f"Successfully downloaded: {chapter.title}")

                except Exception as e:
                    logger.error(f"Failed to download chapter {chapter.title}: {e}")
                    # Error Handling: If the download fails, change the status to failed so we can track it.
                    chapter.status = 'failed'

                    history = DownloadHistory(
                        chapter_id=chapter.id,
                        story_id=story.id,
                        status='failed',
                        details=str(e)
                    )
                    session.add(history)

                    session.commit()

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                session.rollback()
                # Break to avoid infinite loop on DB error
                break
            finally:
                session.close()

        logger.info("Download queue empty or processing stopped.")
