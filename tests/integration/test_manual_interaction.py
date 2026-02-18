import os
import unittest
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import MagicMock
from unittest.mock import MagicMock, patch
from scrollarr.database import Base, engine, SessionLocal, Story, Chapter
from scrollarr.story_manager import StoryManager

# Ensure we use a test database
os.environ['DATABASE_URL'] = 'sqlite:///test_manual.db'

class TestManualInteraction(unittest.TestCase):
    def setUp(self):
        # Create tables
        Base.metadata.create_all(bind=engine)

        # Patch init_db to avoid migration errors in test environment
        with patch('scrollarr.story_manager.init_db'):
            self.manager = StoryManager()

        # Mock provider
        self.mock_provider = MagicMock()
        self.mock_provider.get_metadata.return_value = {
            'title': 'Test Story',
            'author': 'Test Author',
            'cover_url': 'http://example.com/cover.jpg'
        }
        self.mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/1'},
            {'title': 'Chapter 2', 'url': 'http://example.com/2'}
        ]

        # Inject mock provider.
        # SourceManager.get_provider_for_url usually iterates registered providers.
        # We can mock get_provider_for_url directly on the source_manager instance.
        self.manager.source_manager.get_provider_for_url = MagicMock(return_value=self.mock_provider)

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)
        if os.path.exists("test_manual.db"):
            os.remove("test_manual.db")

    def test_check_story_updates(self):
        # 1. Add story with 2 chapters
        story_id = self.manager.add_story("http://example.com/story")

        # 2. Update provider to have 3 chapters
        self.mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/1'},
            {'title': 'Chapter 2', 'url': 'http://example.com/2'},
            {'title': 'Chapter 3', 'url': 'http://example.com/3'}
        ]

        # 3. Call check_story_updates
        new_count = self.manager.check_story_updates(story_id)

        # 4. Verify
        self.assertEqual(new_count, 1)

        session = SessionLocal()
        chapters = session.query(Chapter).filter(Chapter.story_id == story_id).all()
        self.assertEqual(len(chapters), 3)
        session.close()

    def test_retry_failed_chapters(self):
        # 1. Add story
        story_id = self.manager.add_story("http://example.com/story")

        # 2. Mark a chapter as failed
        session = SessionLocal()
        chapter = session.query(Chapter).filter(Chapter.story_id == story_id, Chapter.index == 1).first()
        chapter.status = 'failed'
        session.commit()
        session.close()

        # 3. Call retry
        count = self.manager.retry_failed_chapters(story_id)

        # 4. Verify
        self.assertEqual(count, 1)

        session = SessionLocal()
        chapter = session.query(Chapter).filter(Chapter.story_id == story_id, Chapter.index == 1).first()
        self.assertEqual(chapter.status, 'pending')
        session.close()

if __name__ == '__main__':
    unittest.main()
