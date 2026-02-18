import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import os
import sys

# Add root to sys.path to allow importing modules
sys.path.append(os.getcwd())

from import_manager import ImportManager

class TestImportManager(unittest.TestCase):
    def setUp(self):
        # Patch StoryManager and LibraryManager init to avoid actual DB/File ops during init
        with patch('import_manager.StoryManager'), patch('import_manager.LibraryManager'):
            self.im = ImportManager()

        # Mock the instances
        self.im.story_manager = MagicMock()
        self.im.library_manager = MagicMock()

    @patch('import_manager.os.walk')
    @patch('import_manager.epub.read_epub')
    @patch('import_manager.Path')
    def test_scan_directory(self, mock_path_cls, mock_read_epub, mock_walk):
        # Mock Path root object
        mock_root_path = MagicMock()
        mock_root_path.resolve.return_value = mock_root_path
        mock_root_path.exists.return_value = True
        mock_root_path.is_dir.return_value = True

        # Configure __truediv__ to return a mock with correct name
        def div_side_effect(other):
             m = MagicMock()
             m.name = other
             m.stem = other.split('.')[0]
             m.__str__.return_value = f"/lib/{other}"
             return m

        mock_root_path.__truediv__.side_effect = div_side_effect
        mock_path_cls.return_value = mock_root_path

        # Setup mock directory structure
        mock_walk.return_value = [
            ('/lib', [], ['book.epub', 'other.txt'])
        ]

        # Setup mock epub
        mock_book = MagicMock()
        mock_book.get_metadata.side_effect = lambda ns, key: [['Test Title']] if key == 'title' else [['Test Author']]
        mock_read_epub.return_value = mock_book

        results = self.im.scan_directory('/lib')

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Test Title')
        self.assertEqual(results[0]['author'], 'Test Author')
        self.assertEqual(results[0]['filename'], 'book.epub')

    @patch('import_manager.epub.read_epub')
    def test_extract_metadata_error(self, mock_read_epub):
        mock_read_epub.side_effect = Exception("Corrupt file")

        path = MagicMock()
        path.stem = 'corrupt'
        path.name = 'corrupt.epub'
        path.__str__.return_value = '/lib/corrupt.epub'

        metadata = self.im.extract_metadata(path)

        self.assertEqual(metadata['title'], 'corrupt') # fallback to stem
        self.assertEqual(metadata['author'], 'Unknown')
        self.assertIn('error', metadata)

    def test_import_story(self):
        self.im.story_manager.add_story.return_value = 123

        story_id = self.im.import_story("http://example.com", None, False)

        self.im.story_manager.add_story.assert_called_with("http://example.com")
        self.assertEqual(story_id, 123)

if __name__ == '__main__':
    unittest.main()
