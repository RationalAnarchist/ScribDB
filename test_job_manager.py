import unittest
from unittest.mock import MagicMock, patch, mock_open
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Story, Chapter
from job_manager import JobManager

class TestJobManager(unittest.TestCase):
    def setUp(self):
        # Use in-memory SQLite for testing
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Patch SessionLocal to return our test session
        self.session_mock = MagicMock(wraps=self.session)
        self.session_mock.close = MagicMock()
        self.session_patcher = patch('job_manager.SessionLocal', return_value=self.session_mock)
        self.session_patcher.start()

        # Patch init_db
        self.init_db_patcher = patch('job_manager.init_db')
        self.init_db_patcher.start()

        # Patch config_manager to avoid file I/O
        self.config_patcher = patch('job_manager.config_manager')
        self.mock_config = self.config_patcher.start()
        self.mock_config.get.return_value = "dummy_path"

        # Patch BackgroundScheduler to avoid starting real scheduler
        self.scheduler_patcher = patch('job_manager.BackgroundScheduler')
        self.scheduler_patcher.start()

        # Patch NotificationManager
        self.notification_manager_patcher = patch('job_manager.NotificationManager')
        self.mock_notification_manager_class = self.notification_manager_patcher.start()
        self.mock_notification_manager = self.mock_notification_manager_class.return_value

    def tearDown(self):
        self.session_patcher.stop()
        self.init_db_patcher.stop()
        self.config_patcher.stop()
        self.scheduler_patcher.stop()
        self.notification_manager_patcher.stop()
        self.session.close()
        Base.metadata.drop_all(self.engine)

    @patch('job_manager.StoryManager')
    def test_check_for_updates_monitored_story_with_updates(self, MockStoryManager):
        # Setup JobManager
        jm = JobManager()
        # Ensure the mocked StoryManager is used
        jm.story_manager = MockStoryManager.return_value

        # Setup data
        story = Story(title="Test Story", author="Author", source_url="http://example.com/story", is_monitored=True)
        self.session.add(story)
        self.session.commit()

        # Run function
        jm.check_for_updates()

        # Verify StoryManager.check_story_updates was called
        jm.story_manager.check_story_updates.assert_called_with(story.id)

    @patch('job_manager.StoryManager')
    def test_check_for_updates_monitored_story_no_updates(self, MockStoryManager):
        jm = JobManager()
        jm.story_manager = MockStoryManager.return_value

        # Setup data
        story = Story(title="Test Story", author="Author", source_url="http://example.com/story", is_monitored=True)
        self.session.add(story)
        self.session.commit()

        jm.check_for_updates()

        jm.story_manager.check_story_updates.assert_called_with(story.id)

    @patch('job_manager.StoryManager')
    def test_check_for_updates_not_monitored_story(self, MockStoryManager):
        jm = JobManager()
        jm.story_manager = MockStoryManager.return_value

        story = Story(title="Test Story", author="Author", source_url="http://example.com/story", is_monitored=False)
        self.session.add(story)
        self.session.commit()

        jm.check_for_updates()

        jm.story_manager.check_story_updates.assert_not_called()

    @patch('job_manager.StoryManager')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_process_download_queue(self, mock_makedirs, mock_file, MockStoryManager):
        jm = JobManager()
        jm.story_manager = MockStoryManager.return_value

        # Setup data
        story = Story(title="Test Story", author="Author", source_url="http://example.com/story", is_monitored=True)
        self.session.add(story)
        self.session.commit()

        chapter = Chapter(title="Chapter 1", source_url="http://example.com/ch1", story_id=story.id, status='pending')
        self.session.add(chapter)
        self.session.commit()

        mock_provider = MagicMock()
        jm.story_manager.source_manager.get_provider_for_url.return_value = mock_provider

        mock_provider.get_chapter_content.return_value = "<html>Content</html>"

        jm.process_download_queue()

        mock_provider.get_chapter_content.assert_called_with("http://example.com/ch1")
        mock_file.assert_called()
        mock_file().write.assert_called_with("<html>Content</html>")

        updated_chapter = self.session.query(Chapter).filter(Chapter.id == chapter.id).first()
        self.assertEqual(updated_chapter.status, 'downloaded')
        self.assertTrue(updated_chapter.is_downloaded)

if __name__ == '__main__':
    unittest.main()
