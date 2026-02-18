import unittest
import os
import sys
sys.path.append(os.getcwd())
import shutil
import glob
from unittest.mock import MagicMock, patch
from scrollarr.story_manager import StoryManager
from scrollarr.database import Story, Chapter, DownloadHistory, SessionLocal
from scrollarr.config import config_manager

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

    @patch('scrollarr.story_manager.init_db')
    @patch('scrollarr.story_manager.StoryManager.reload_providers')
    @patch('scrollarr.story_manager.SessionLocal')
    @patch('scrollarr.config.ConfigManager.get')
    def test_delete_story_with_content(self, mock_config_get, MockSessionLocal, mock_reload, mock_init_db):
        # Setup mock config
        mock_config_get.side_effect = lambda key, default=None: {
            'download_path': self.download_path,
            'library_path': self.library_path,
            'story_folder_format': '{Title} ({Id})',
            'compiled_filename_pattern': '{Title} - {Volume}'
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
        # 1. New Structure: library_path/Delete Me (1)
        story_dir = os.path.join(self.library_path, "Delete Me (1)")
        os.makedirs(story_dir, exist_ok=True)
        # Compiled dir
        compiled_dir = os.path.join(story_dir, "compiled")
        os.makedirs(compiled_dir, exist_ok=True)

        # Ebook inside compiled dir (standard structure)
        # Assuming LibraryManager puts compiled files in compiled_dir
        ebook_filename = "Delete Me - Vol 1.epub"
        ebook_path = os.path.join(compiled_dir, ebook_filename)
        with open(ebook_path, "w") as f:
            f.write("ebook content")

        # 2. Legacy Structure: download_path/1_Delete_Me
        legacy_dir = os.path.join(self.download_path, "1_Delete_Me")
        os.makedirs(legacy_dir, exist_ok=True)

        # Initialize manager
        manager = StoryManager()

        # Execute delete
        manager.delete_story(1, delete_content=True)

        # Verify files are gone
        self.assertFalse(os.path.exists(story_dir), "Story directory should be deleted")
        self.assertFalse(os.path.exists(legacy_dir), "Legacy directory should be deleted")

        # Verify DB interactions
        mock_session.delete.assert_called_with(story)
        mock_session.commit.assert_called()

    @patch('scrollarr.story_manager.init_db')
    @patch('scrollarr.story_manager.StoryManager.reload_providers')
    @patch('scrollarr.story_manager.SessionLocal')
    @patch('scrollarr.config.ConfigManager.get')
    def test_delete_story_no_content(self, mock_config_get, MockSessionLocal, mock_reload, mock_init_db):
        # Setup mock config
        mock_config_get.side_effect = lambda key, default=None: {
            'download_path': self.download_path,
            'library_path': self.library_path,
            'story_folder_format': '{Title} ({Id})'
        }.get(key, default)

        # Setup mock session
        mock_session = MagicMock()
        MockSessionLocal.return_value = mock_session

        story = MagicMock(spec=Story)
        story.id = 2
        story.title = "Keep Files"
        story.author = "Test Author"
        story.chapters = []
        mock_session.query.return_value.filter.return_value.first.return_value = story

        # Create files
        story_dir = os.path.join(self.library_path, "Keep Files (2)")
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
