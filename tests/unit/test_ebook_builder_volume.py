import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import sys

# Ensure current directory is in sys.path
sys.path.append(os.getcwd())

from scrollarr.ebook_builder import EbookBuilder

class TestEbookBuilderVolume(unittest.TestCase):
    def setUp(self):
        self.builder = EbookBuilder()

    @patch('scrollarr.config.ConfigManager.get')
    @patch('scrollarr.database.Chapter')
    @patch('scrollarr.database.Story')
    @patch('scrollarr.database.SessionLocal')
    @patch.object(EbookBuilder, 'make_epub')
    def test_compile_volume_success(self, mock_make_epub, MockSessionLocal, MockStory, MockChapter, mock_config_get):
        # Setup mock config
        mock_config_get.side_effect = lambda key, default=None: {
            'library_path': 'library',
            'filename_pattern': '{Title} - {Volume}',
            'compiled_filename_pattern': '{Title} - {Volume}',
            'volume_name_format': '{Title} - {Volume}'
        }.get(key, default)

        # Setup mock session
        mock_session = MagicMock()
        MockSessionLocal.return_value = mock_session

        # Setup mock story
        story = MagicMock()
        story.id = 1
        story.title = "Test Story"
        story.author = "Test Author"
        story.cover_path = "cover.jpg"
        story.profile = None

        # Setup mock chapters
        chapter1 = MagicMock()
        chapter1.title = "Chapter 1"
        chapter1.local_path = "path/to/1.html"
        chapter1.index = 1
        chapter1.volume_title = None
        chapter1.volume_number = 1

        chapter2 = MagicMock()
        chapter2.title = "Chapter 2"
        chapter2.local_path = "path/to/2.html"
        chapter2.index = 2
        chapter2.volume_number = 1

        # Configure query return values
        # We need to handle the query chain: session.query(Model).filter(...).first() or .all()

        def query_side_effect(model):
            q = MagicMock()
            if model == MockStory:
                # filter().first() -> story
                q.filter.return_value.first.return_value = story
            elif model == MockChapter:
                # filter().order_by().all() -> [chapter1, chapter2]
                q.filter.return_value.order_by.return_value.all.return_value = [chapter1, chapter2]
            return q

        mock_session.query.side_effect = query_side_effect

        # Mock file operations
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data="<p>Content</p>")):
                with patch('os.makedirs') as mock_makedirs:
                    output_path = self.builder.compile_volume(1, 1)
                    # Verify makedirs called (ensure_directories)
                    # It might be called multiple times.
                    mock_makedirs.assert_called()

        # Verify assertions
        # Expected filename logic: {Title} - {Volume}.epub -> Test Story - Vol 1.epub
        # And it should be in library/Test Story (1)/compiled/

        # LibraryManager: get_compiled_dir -> library/Test Story (1)/compiled
        # get_compiled_filename -> Test Story - Vol 1.epub

        expected_filename = "library/Test Story (1)/compiled/Test Story - Vol 1.epub"

        # Since os.path.join uses OS separator, let's normalize check or construct expected
        expected_path = os.path.abspath(os.path.join('library', 'Test Story (1)', 'compiled', 'Test Story - Vol 1.epub'))

        # The return value is string
        self.assertEqual(os.path.normpath(output_path), os.path.normpath(expected_path))

        expected_chapters = [
            {'title': 'Chapter 1', 'content': '<p>Content</p>'},
            {'title': 'Chapter 2', 'content': '<p>Content</p>'}
        ]

        # Title passed to make_epub is "{story.title} - {suffix}" -> "Test Story - Vol 1"
        mock_make_epub.assert_called_once()
        args, kwargs = mock_make_epub.call_args
        self.assertEqual(args[0], "Test Story - Vol 1")
        self.assertEqual(args[1], "Test Author")
        self.assertEqual(args[2], expected_chapters)
        self.assertEqual(os.path.normpath(args[3]), os.path.normpath(expected_path))

        mock_session.close.assert_called_once()

    @patch('scrollarr.database.Story')
    @patch('scrollarr.database.SessionLocal')
    def test_compile_volume_story_not_found(self, MockSessionLocal, MockStory):
        mock_session = MagicMock()
        MockSessionLocal.return_value = mock_session

        # Mock Story query to return None
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with self.assertRaisesRegex(ValueError, "Story with ID 999 not found"):
            self.builder.compile_volume(999, 1)

        mock_session.close.assert_called_once()

    @patch('scrollarr.database.Chapter')
    @patch('scrollarr.database.Story')
    @patch('scrollarr.database.SessionLocal')
    def test_compile_volume_no_chapters(self, MockSessionLocal, MockStory, MockChapter):
        mock_session = MagicMock()
        MockSessionLocal.return_value = mock_session

        story = MagicMock()
        story.title = "Test Story"

        def query_side_effect(model):
            q = MagicMock()
            if model == MockStory:
                q.filter.return_value.first.return_value = story
            elif model == MockChapter:
                q.filter.return_value.order_by.return_value.all.return_value = []
            return q

        mock_session.query.side_effect = query_side_effect

        with self.assertRaisesRegex(ValueError, "No chapters found for volume 1"):
            self.builder.compile_volume(1, 1)

        mock_session.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()
