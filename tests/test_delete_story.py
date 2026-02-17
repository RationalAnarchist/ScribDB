import unittest
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shutil
import glob
from unittest.mock import MagicMock, patch
from story_manager import StoryManager
from database import Story, Chapter, DownloadHistory, SessionLocal
from config import config_manager

class TestDeleteStory(unittest.TestCase):
    def setUp(self):
        # Setup mock environment
        self.download_path = "test_downloads"
        self.library_path = "test_library"
        os.makedirs(self.download_path, exist_ok=True)
        os.makedirs(self.library_path, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.download_path):
            shutil.rmtree(self.download_path)
        if os.path.exists(self.library_path):
            shutil.rmtree(self.library_path)

    @patch('story_manager.init_db')
    @patch('story_manager.StoryManager.reload_providers')
    @patch('story_manager.SessionLocal')
    @patch('story_manager.config_manager')
    def test_delete_story_with_content(self, mock_config_manager, MockSessionLocal, mock_reload, mock_init_db):
        # Setup mock config
        mock_config_manager.get.side_effect = lambda key, default=None: {
            'download_path': self.download_path,
            'library_path': self.library_path,
            'filename_pattern': '{Title} - Vol {Volume}'
        }.get(key, default)

        # Setup mock session and data
        mock_session = MagicMock()
        MockSessionLocal.return_value = mock_session

        story = MagicMock(spec=Story)
        story.id = 1
        story.title = "Delete Me"
        story.author = "Test Author"

        # Mock chapters to determine volumes
        chapter1 = MagicMock(spec=Chapter)
        chapter1.volume_number = 1
        story.chapters = [chapter1]

        # Configure query to return story
        mock_session.query.return_value.filter.return_value.first.return_value = story

        # Create physical files to test deletion
        # 1. Story Directory
        safe_title = "Delete_Me" # Simple logic from code: Delete Me -> Delete_Me
        story_dir = os.path.join(self.download_path, f"{story.id}_{safe_title}")
        os.makedirs(story_dir, exist_ok=True)
        with open(os.path.join(story_dir, "test_chap.html"), "w") as f:
            f.write("test content")

        # 2. Ebook
        # Filename: Delete Me - Vol Vol 1.epub (based on my findings of double Vol)
        ebook_filename = "Delete Me - Vol Vol 1.epub"
        ebook_path = os.path.join(self.library_path, ebook_filename)
        with open(ebook_path, "w") as f:
            f.write("ebook content")

        # Verify files exist
        self.assertTrue(os.path.exists(story_dir))
        self.assertTrue(os.path.exists(ebook_path))

        # Initialize manager
        manager = StoryManager()

        # Execute delete
        manager.delete_story(1, delete_content=True)

        # Verify files are gone
        self.assertFalse(os.path.exists(story_dir), "Story directory should be deleted")
        self.assertFalse(os.path.exists(ebook_path), "Ebook file should be deleted")

        # Verify DB interactions
        mock_session.delete.assert_called_with(story)
        mock_session.commit.assert_called()

    @patch('story_manager.init_db')
    @patch('story_manager.StoryManager.reload_providers')
    @patch('story_manager.SessionLocal')
    @patch('story_manager.config_manager')
    def test_delete_story_no_content(self, mock_config_manager, MockSessionLocal, mock_reload, mock_init_db):
        # Setup mock config
        mock_config_manager.get.side_effect = lambda key, default=None: {
            'download_path': self.download_path,
            'library_path': self.library_path,
        }.get(key, default)

        # Setup mock session
        mock_session = MagicMock()
        MockSessionLocal.return_value = mock_session

        story = MagicMock(spec=Story)
        story.id = 2
        story.title = "Keep Files"
        story.chapters = []
        mock_session.query.return_value.filter.return_value.first.return_value = story

        # Create files
        story_dir = os.path.join(self.download_path, "2_Keep_Files")
        os.makedirs(story_dir, exist_ok=True)

        # Execute delete
        manager = StoryManager()
        manager.delete_story(2, delete_content=False)

        # Verify files still exist
        self.assertTrue(os.path.exists(story_dir))

        # Verify DB delete called
        mock_session.delete.assert_called_with(story)

if __name__ == '__main__':
    unittest.main()
