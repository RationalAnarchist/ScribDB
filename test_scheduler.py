import unittest
from unittest.mock import MagicMock, patch, mock_open
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Story, Chapter
from scheduler import check_for_updates, process_download_queue

class TestScheduler(unittest.TestCase):
    def setUp(self):
        # Use in-memory SQLite for testing
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Patch SessionLocal to return our test session
        # We need to wrap the session so that close() calls in the code don't actually close the test session
        self.session_mock = MagicMock(wraps=self.session)
        self.session_mock.close = MagicMock()
        self.session_patcher = patch('scheduler.SessionLocal', return_value=self.session_mock)
        self.session_patcher.start()

        # Patch init_db to prevent side effects
        self.init_db_patcher = patch('scheduler.init_db')
        self.init_db_patcher.start()

    def tearDown(self):
        self.session_patcher.stop()
        self.init_db_patcher.stop()
        self.session.close()
        Base.metadata.drop_all(self.engine)

    @patch('scheduler.StoryManager')
    def test_check_for_updates_monitored_story_with_updates(self, MockStoryManager):
        # Setup data
        story = Story(title="Test Story", author="Author", source_url="http://example.com/story", is_monitored=True)
        self.session.add(story)
        self.session.commit()

        # Add 1 local chapter
        chapter = Chapter(title="Chapter 1", source_url="http://example.com/ch1", story_id=story.id)
        self.session.add(chapter)
        self.session.commit()

        # Mock StoryManager and SourceManager
        mock_story_manager = MockStoryManager.return_value
        mock_provider = MagicMock()
        mock_story_manager.source_manager.get_provider_for_url.return_value = mock_provider

        # Mock remote chapters (2 chapters, so 1 new)
        mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/ch1'},
            {'title': 'Chapter 2', 'url': 'http://example.com/ch2'}
        ]

        # Run function
        check_for_updates()

        # Verify new chapter was added
        chapters = self.session.query(Chapter).filter(Chapter.story_id == story.id).all()
        self.assertEqual(len(chapters), 2)
        new_chapter = next(c for c in chapters if c.source_url == 'http://example.com/ch2')
        self.assertEqual(new_chapter.title, 'Chapter 2')
        self.assertEqual(new_chapter.status, 'pending')

    @patch('scheduler.StoryManager')
    def test_check_for_updates_monitored_story_no_updates(self, MockStoryManager):
        # Setup data
        story = Story(title="Test Story", author="Author", source_url="http://example.com/story", is_monitored=True)
        self.session.add(story)
        self.session.commit()

        # Add 1 local chapter
        chapter = Chapter(title="Chapter 1", source_url="http://example.com/ch1", story_id=story.id)
        self.session.add(chapter)
        self.session.commit()

        # Mock StoryManager and SourceManager
        mock_story_manager = MockStoryManager.return_value
        mock_provider = MagicMock()
        mock_story_manager.source_manager.get_provider_for_url.return_value = mock_provider

        # Mock remote chapters (same count)
        mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/ch1'}
        ]

        # Run function
        check_for_updates()

        # Verify no new chapters added
        chapters = self.session.query(Chapter).filter(Chapter.story_id == story.id).all()
        self.assertEqual(len(chapters), 1)

    @patch('scheduler.StoryManager')
    def test_check_for_updates_not_monitored_story(self, MockStoryManager):
        # Setup data
        story = Story(title="Test Story", author="Author", source_url="http://example.com/story", is_monitored=False)
        self.session.add(story)
        self.session.commit()

        # Mock StoryManager and SourceManager
        mock_story_manager = MockStoryManager.return_value
        mock_provider = MagicMock()
        mock_story_manager.source_manager.get_provider_for_url.return_value = mock_provider

        # Run function
        check_for_updates()

        # Verify provider was NOT called
        mock_provider.get_chapter_list.assert_not_called()

    @patch('scheduler.StoryManager')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_process_download_queue(self, mock_makedirs, mock_file, MockStoryManager):
        # Setup data
        story = Story(title="Test Story", author="Author", source_url="http://example.com/story", is_monitored=True)
        self.session.add(story)
        self.session.commit()

        chapter = Chapter(title="Chapter 1", source_url="http://example.com/ch1", story_id=story.id, status='pending')
        self.session.add(chapter)
        self.session.commit()

        # Mock StoryManager and SourceManager
        mock_story_manager = MockStoryManager.return_value
        mock_provider = MagicMock()
        mock_story_manager.source_manager.get_provider_for_url.return_value = mock_provider

        # Mock content
        mock_provider.get_chapter_content.return_value = "<html>Content</html>"

        # Run function
        process_download_queue()

        # Verify provider called
        mock_provider.get_chapter_content.assert_called_with("http://example.com/ch1")

        # Verify file written
        mock_file.assert_called()
        mock_file().write.assert_called_with("<html>Content</html>")

        # Verify status updated
        updated_chapter = self.session.query(Chapter).filter(Chapter.id == chapter.id).first()
        self.assertEqual(updated_chapter.status, 'downloaded')
        self.assertTrue(updated_chapter.is_downloaded)
        self.assertIsNotNone(updated_chapter.local_path)

if __name__ == '__main__':
    unittest.main()
