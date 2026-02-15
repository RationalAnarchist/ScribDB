import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Story, Chapter
from scheduler import check_for_updates

class TestScheduler(unittest.TestCase):
    def setUp(self):
        # Use in-memory SQLite for testing
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Patch SessionLocal to return our test session
        self.session_patcher = patch('scheduler.SessionLocal', return_value=self.session)
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

        # Verify add_story was called
        mock_story_manager.add_story.assert_called_with("http://example.com/story")

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

        # Verify add_story was NOT called
        mock_story_manager.add_story.assert_not_called()

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

        # Verify provider was NOT called (loop should be empty)
        mock_provider.get_chapter_list.assert_not_called()
        mock_story_manager.add_story.assert_not_called()

if __name__ == '__main__':
    unittest.main()
