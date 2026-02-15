import logging
from database import SessionLocal, Story, init_db
from story_manager import StoryManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_for_updates():
    """
    Iterates through all 'Monitored' stories in the database.
    Checks if the remote chapter count is higher than the local database count.
    If new chapters are found, adds them to the download queue.
    """
    logger.info("Starting update check...")

    # Ensure database is initialized and migrated
    init_db()

    session = SessionLocal()
    story_manager = StoryManager()

    try:
        # Query monitored stories
        monitored_stories = session.query(Story).filter(Story.is_monitored == True).all()

        logger.info(f"Found {len(monitored_stories)} monitored stories.")

        for story in monitored_stories:
            logger.info(f"Checking updates for '{story.title}'...")

            # Get provider
            provider = story_manager.source_manager.get_provider_for_url(story.source_url)
            if not provider:
                logger.warning(f"No provider found for story: {story.title} ({story.source_url})")
                continue

            try:
                # Fetch remote chapter list
                remote_chapters = provider.get_chapter_list(story.source_url)
                remote_count = len(remote_chapters)

                # Get local chapter count
                local_count = len(story.chapters)

                logger.info(f"'{story.title}': Remote count {remote_count}, Local count {local_count}")

                if remote_count > local_count:
                    logger.info(f"New chapters found for '{story.title}'! Updating...")
                    # Update story (adds new chapters)
                    story_manager.add_story(story.source_url)
                else:
                    logger.info(f"No new chapters for '{story.title}'.")

            except Exception as e:
                logger.error(f"Error checking updates for '{story.title}': {e}")

    except Exception as e:
        logger.error(f"Error during update check: {e}")
    finally:
        session.close()
        logger.info("Update check complete.")

if __name__ == "__main__":
    check_for_updates()
