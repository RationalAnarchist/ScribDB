import logging
import time
import os
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func
from database import SessionLocal, Story, Chapter, DownloadHistory, init_db
from story_manager import StoryManager
from notifications import NotificationManager
from config import config_manager
from library_manager import LibraryManager

# Configure logging
logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.story_manager = StoryManager()
        self.notification_manager = NotificationManager()
        self.library_manager = LibraryManager()
        self.running = False

    def start(self):
        """Starts the scheduler with configured jobs."""
        init_db()
        self.running = True
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

        # Schedule immediate run of updates check on startup
        self.scheduler.add_job(
            self.check_for_updates,
            'date',
            run_date=datetime.now() + timedelta(seconds=20),
            id='check_updates_startup'
        )

        logger.info("JobManager started.")

    def stop(self):
        """Stops the scheduler."""
        self.running = False
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("JobManager stopped.")

    def pause(self):
        """Pauses the scheduler and stops running jobs."""
        self.running = False
        if self.scheduler.running:
            self.scheduler.pause()
        logger.info("JobManager paused.")

    def resume(self):
        """Resumes the scheduler."""
        self.running = True
        if self.scheduler.running:
            self.scheduler.resume()
        else:
            self.start()
        logger.info("JobManager resumed.")

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
            if not self.running:
                logger.info("Stopping update check due to shutdown signal.")
                break

            try:
                self.story_manager.check_story_updates(story_id)
            except Exception as e:
                logger.error(f"Error updating story {story_id}: {e}")

    def process_download_queue(self):
        """
        Downloads pending chapters until queue is empty.
        """
        logger.info("Checking download queue for pending chapters...")

        while self.running:
            session = SessionLocal()
            try:
                # Prioritize stories with fewer pending chapters
                # 1. Count pending chapters per story
                subquery = (
                    session.query(Chapter.story_id, func.count(Chapter.id).label('pending_count'))
                    .filter(Chapter.status == 'pending')
                    .group_by(Chapter.story_id)
                    .subquery()
                )

                # 2. Find the story with the fewest pending chapters
                best_story_row = (
                    session.query(subquery.c.story_id)
                    .order_by(subquery.c.pending_count.asc())
                    .first()
                )

                chapter = None
                if best_story_row:
                    # 3. Get the oldest pending chapter for that story
                    chapter = (
                        session.query(Chapter)
                        .filter(Chapter.story_id == best_story_row.story_id, Chapter.status == 'pending')
                        .order_by(Chapter.id.asc())
                        .with_for_update()
                        .first()
                    )

                # Fallback to global oldest if priority selection fails (e.g. race condition)
                if not chapter:
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

                    # Use LibraryManager for path
                    filepath = self.library_manager.get_chapter_absolute_path(story, chapter)
                    self.library_manager.ensure_directories(filepath.parent)

                    # Write file to disk
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                    # The Update: Once the file is written to disk, update the status from pending to downloaded.
                    chapter.local_path = str(filepath)
                    chapter.is_downloaded = True
                    chapter.status = 'downloaded'

                    history = DownloadHistory(
                        chapter_id=chapter.id,
                        story_id=story.id,
                        status='downloaded',
                        details=f"Downloaded successfully to {os.path.basename(filepath)}"
                    )
                    session.add(history)

                    session.commit()
                    logger.info(f"Successfully downloaded: {chapter.title}")

                    # Check for remaining pending/failed chapters for this story
                    remaining_count = session.query(Chapter).filter(
                        Chapter.story_id == story.id,
                        Chapter.status.in_(['pending', 'failed'])
                    ).count()

                    if remaining_count == 0:
                        logger.info(f"Story {story.title} download complete (no pending/failed chapters). Compiling full ebook...")

                        try:
                            # Compile full story
                            from ebook_builder import EbookBuilder
                            builder = EbookBuilder()
                            ebook_path = builder.compile_full_story(story.id)

                            logger.info(f"Full story compiled at {ebook_path}")

                            # Notify success with full ebook
                            self.notification_manager.dispatch('on_download', {
                                'story_title': story.title,
                                'chapter_title': "Full Story Download",
                                'chapter_id': chapter.id,
                                'story_id': story.id,
                                'file_path': ebook_path
                            })

                        except Exception as e:
                            logger.error(f"Failed to compile full story ebook: {e}")
                            self.notification_manager.dispatch('on_failure', {
                                'story_title': story.title,
                                'chapter_title': "Ebook Compilation",
                                'story_id': story.id,
                                'error': f"Failed to compile ebook: {str(e)}"
                            })
                    else:
                        logger.debug(f"Story {story.title} has {remaining_count} remaining items. Skipping notification.")

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

                    # Notify failure
                    self.notification_manager.dispatch('on_failure', {
                        'story_title': story.title,
                        'chapter_title': chapter.title,
                        'chapter_id': chapter.id,
                        'story_id': story.id,
                        'error': str(e)
                    })

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                session.rollback()
                # Break to avoid infinite loop on DB error
                break
            finally:
                session.close()

        logger.info("Download queue empty or processing stopped.")
