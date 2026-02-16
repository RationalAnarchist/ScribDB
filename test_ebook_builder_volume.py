import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import sys

# Ensure the current directory is in sys.path so we can import modules
sys.path.append(os.getcwd())

from ebook_builder import EbookBuilder

class TestEbookBuilderVolume(unittest.TestCase):
    def setUp(self):
        self.builder = EbookBuilder()

    @patch('database.Chapter')
    @patch('database.Story')
    @patch('database.SessionLocal')
    @patch.object(EbookBuilder, 'make_epub')
    def test_compile_volume_success(self, mock_make_epub, MockSessionLocal, MockStory, MockChapter):
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

        chapter2 = MagicMock()
        chapter2.title = "Chapter 2"
        chapter2.local_path = "path/to/2.html"
        chapter2.index = 2

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
                output_path = self.builder.compile_volume(1, 1)

        # Verify assertions
        expected_title = "Test Story - Vol 1"
        expected_filename = "Test_Story_-_Vol_1.epub"
        self.assertEqual(output_path, expected_filename)

        expected_chapters = [
            {'title': 'Chapter 1', 'content': '<p>Content</p>'},
            {'title': 'Chapter 2', 'content': '<p>Content</p>'}
        ]

        mock_make_epub.assert_called_once_with(
            expected_title,
            "Test Author",
            expected_chapters,
            expected_filename,
            "cover.jpg",
            css=None
        )
        mock_session.close.assert_called_once()

    @patch('database.Story')
    @patch('database.SessionLocal')
    def test_compile_volume_story_not_found(self, MockSessionLocal, MockStory):
        mock_session = MagicMock()
        MockSessionLocal.return_value = mock_session

        # Mock Story query to return None
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with self.assertRaisesRegex(ValueError, "Story with ID 999 not found"):
            self.builder.compile_volume(999, 1)

        mock_session.close.assert_called_once()

    @patch('database.Chapter')
    @patch('database.Story')
    @patch('database.SessionLocal')
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
