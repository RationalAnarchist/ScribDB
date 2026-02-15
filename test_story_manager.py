import os

# Set environment variable for test database
os.environ['DATABASE_URL'] = 'sqlite:///test_library.db'

import unittest
import shutil
from unittest.mock import MagicMock
from story_manager import StoryManager
from database import Story, Chapter, SessionLocal, Base, engine

class TestStoryManager(unittest.TestCase):
    def setUp(self):
        # Drop all tables and recreate them to ensure clean state
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

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
        Base.metadata.drop_all(bind=engine)

        # Dispose engine connections
        engine.dispose()

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
        session = SessionLocal()
        story = session.query(Story).filter(Story.id == story_id).first()
        self.assertIsNotNone(story)
        self.assertEqual(story.title, 'Test Story')
        self.assertEqual(len(story.chapters), 2)
        session.close()

    def test_download_missing_chapters(self):
        # First add the story
        story_id = self.manager.add_story("http://example.com/story")

        # Run download
        self.manager.download_missing_chapters(story_id)

        # Verify DB updates
        session = SessionLocal()
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

if __name__ == '__main__':
    unittest.main()
