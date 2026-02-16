import os

# Set environment variable for test database
os.environ['DATABASE_URL'] = 'sqlite:///test_library.db'

import unittest
import shutil
from unittest.mock import MagicMock
from story_manager import StoryManager
from database import Story, Chapter, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database
from unittest.mock import patch

class TestStoryManager(unittest.TestCase):
    def setUp(self):
        # Create new engine/session pointing to test DB
        self.test_db_url = 'sqlite:///test_library.db'
        self.test_engine = create_engine(self.test_db_url, connect_args={"check_same_thread": False})
        self.TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.test_engine)

        # Patch database module (for modules that import it dynamically or use database.SessionLocal)
        self.original_engine = database.engine
        self.original_sessionlocal = database.SessionLocal
        self.original_db_url = database.DB_URL
        database.engine = self.test_engine
        database.SessionLocal = self.TestSessionLocal
        database.DB_URL = self.test_db_url

        # Patch StoryManager and Notifications imports
        self.sm_session_patcher = patch('story_manager.SessionLocal', self.TestSessionLocal)
        self.sm_session_patcher.start()

        self.notif_session_patcher = patch('notifications.SessionLocal', self.TestSessionLocal)
        self.notif_session_patcher.start()

        # Ensure we start with a clean state
        if os.path.exists("test_library.db"):
            os.remove("test_library.db")

        # Initialize manager (which will run migrations and create DB)
        self.manager = StoryManager()

        # Mock the provider
        self.mock_provider = MagicMock()
        self.mock_provider.identify.return_value = True
        self.mock_provider.get_metadata.return_value = {
            'title': 'Test Story',
            'author': 'Test Author',
            'cover_url': 'http://example.com/cover.jpg'
        }
        self.mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/1'},
            {'title': 'Chapter 2', 'url': 'http://example.com/2'}
        ]
        self.mock_provider.get_chapter_content.return_value = "<p>Test Content</p>"

        # Inject the mock provider
        # We clear existing providers and add our mock
        self.manager.source_manager.providers = [self.mock_provider]

    def tearDown(self):
        # Clean up database tables
        try:
            Base.metadata.drop_all(bind=self.test_engine)
        except:
            pass

        # Stop patches
        self.sm_session_patcher.stop()
        self.notif_session_patcher.stop()

        # Restore database module
        database.engine = self.original_engine
        database.SessionLocal = self.original_sessionlocal
        database.DB_URL = self.original_db_url

        # Dispose test engine
        self.test_engine.dispose()

        # Clean up files
        if os.path.exists("saved_stories"):
            shutil.rmtree("saved_stories")

        # Remove test database file if it exists
        if os.path.exists("test_library.db"):
            try:
                os.remove("test_library.db")
            except OSError:
                pass

    def test_add_story(self):
        story_id = self.manager.add_story("http://example.com/story")

        self.assertIsNotNone(story_id)

        # Verify DB
        session = database.SessionLocal()
        story = session.query(Story).filter(Story.id == story_id).first()
        self.assertIsNotNone(story)
        self.assertEqual(story.title, 'Test Story')
        self.assertEqual(story.status, 'Monitoring')
        self.assertIsNotNone(story.last_updated)
        self.assertEqual(len(story.chapters), 2)

        # Check indices
        chapters = session.query(Chapter).filter(Chapter.story_id == story_id).order_by(Chapter.index).all()
        self.assertEqual(chapters[0].title, 'Chapter 1')
        self.assertEqual(chapters[0].index, 1)
        self.assertEqual(chapters[1].title, 'Chapter 2')
        self.assertEqual(chapters[1].index, 2)

        session.close()

    def test_download_missing_chapters(self):
        # First add the story
        story_id = self.manager.add_story("http://example.com/story")

        # Run download
        self.manager.download_missing_chapters(story_id)

        # Verify DB updates
        session = database.SessionLocal()
        chapters = session.query(Chapter).filter(Chapter.story_id == story_id).all()
        for chapter in chapters:
            self.assertTrue(chapter.is_downloaded)
            self.assertIsNotNone(chapter.local_path)
            self.assertTrue(os.path.exists(chapter.local_path))
            with open(chapter.local_path, 'r') as f:
                content = f.read()
                self.assertEqual(content, "<p>Test Content</p>")
        session.close()

    def test_list_stories(self):
        self.manager.add_story("http://example.com/story")
        stories = self.manager.list_stories()
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]['title'], 'Test Story')
        self.assertEqual(stories[0]['downloaded'], 0)
        self.assertEqual(stories[0]['total'], 2)

        # Download chapters and check again
        story_id = stories[0]['id']
        self.manager.download_missing_chapters(story_id)
        stories = self.manager.list_stories()
        self.assertEqual(stories[0]['downloaded'], 2)

    def test_compile_story(self):
        story_id = self.manager.add_story("http://example.com/story")
        self.manager.download_missing_chapters(story_id)

        output_path = self.manager.compile_story(story_id)
        self.assertTrue(os.path.exists(output_path))
        self.assertTrue(output_path.endswith(".epub"))
        # cleanup epub
        if os.path.exists(output_path):
            os.remove(output_path)

    def test_get_pending_chapters(self):
        story_id = self.manager.add_story("http://example.com/story")
        pending_chapters = self.manager.get_pending_chapters()

        self.assertEqual(len(pending_chapters), 2)
        self.assertEqual(pending_chapters[0].story_id, story_id)
        self.assertEqual(pending_chapters[0].status, 'pending')

        # Verify story is loaded
        self.assertEqual(pending_chapters[0].story.title, 'Test Story')

        # Download chapters
        self.manager.download_missing_chapters(story_id)

        pending_chapters = self.manager.get_pending_chapters()
        self.assertEqual(len(pending_chapters), 0)

    def test_update_library(self):
        # 1. Add a story with 2 chapters
        self.mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/1'},
            {'title': 'Chapter 2', 'url': 'http://example.com/2'}
        ]
        story_id = self.manager.add_story("http://example.com/story")

        # Verify initial state
        session = database.SessionLocal()
        story = session.query(Story).filter(Story.id == story_id).first()
        self.assertEqual(len(story.chapters), 2)
        session.close()

        # 2. Update mock provider to return 3 chapters
        self.mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/1'},
            {'title': 'Chapter 2', 'url': 'http://example.com/2'},
            {'title': 'Chapter 3', 'url': 'http://example.com/3'}
        ]

        # 3. Call update_library
        self.manager.update_library()

        # 4. Verify new chapter is added
        session = database.SessionLocal()
        story = session.query(Story).filter(Story.id == story_id).first()
        self.assertEqual(len(story.chapters), 3)

        # Check specific chapter
        new_chapter = session.query(Chapter).filter(Chapter.source_url == 'http://example.com/3').first()
        self.assertIsNotNone(new_chapter)
        self.assertEqual(new_chapter.title, 'Chapter 3')
        self.assertEqual(new_chapter.status, 'pending')
        self.assertEqual(new_chapter.index, 3)

        session.close()

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

        session = database.SessionLocal()
        chapters = session.query(Chapter).filter(Chapter.story_id == story_id).all()
        self.assertEqual(len(chapters), 3)
        session.close()

    def test_retry_failed_chapters(self):
        # 1. Add story
        story_id = self.manager.add_story("http://example.com/story")

        # 2. Mark a chapter as failed
        session = database.SessionLocal()
        chapter = session.query(Chapter).filter(Chapter.story_id == story_id, Chapter.index == 1).first()
        chapter.status = 'failed'
        session.commit()
        session.close()

        # 3. Call retry
        count = self.manager.retry_failed_chapters(story_id)

        # 4. Verify
        self.assertEqual(count, 1)

        session = database.SessionLocal()
        chapter = session.query(Chapter).filter(Chapter.story_id == story_id, Chapter.index == 1).first()
        self.assertEqual(chapter.status, 'pending')
        session.close()

    def test_fill_missing_metadata(self):
        # 1. Add a story with empty description
        self.mock_provider.get_metadata.return_value = {
            'title': 'Test Story',
            'author': 'Test Author',
            'cover_url': 'http://example.com/cover.jpg',
            'description': '', # Empty description initially
            'tags': 'Tag1'
        }

        story_id = self.manager.add_story("http://example.com/story")

        # Verify initial state
        session = database.SessionLocal()
        story = session.query(Story).filter(Story.id == story_id).first()
        self.assertEqual(story.description, '')
        session.close()

        # 2. Update mock provider to return a description
        self.mock_provider.get_metadata.return_value = {
            'title': 'Test Story',
            'author': 'Test Author',
            'cover_url': 'http://example.com/cover.jpg',
            'description': 'New Description',
            'tags': 'Tag1, Tag2'
        }

        # 3. Call fill_missing_metadata
        self.manager.fill_missing_metadata()

        # 4. Verify description is updated
        session = database.SessionLocal()
        story = session.query(Story).filter(Story.id == story_id).first()
        self.assertEqual(story.description, 'New Description')
        self.assertEqual(story.tags, 'Tag1, Tag2')
        session.close()

if __name__ == '__main__':
    unittest.main()
