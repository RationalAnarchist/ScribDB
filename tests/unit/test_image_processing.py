import unittest
from unittest.mock import MagicMock, patch, mock_open, ANY
import os
from pathlib import Path
from bs4 import BeautifulSoup

# Mock init_db before importing StoryManager if it runs on import?
# It runs inside __init__ of StoryManager.

from scrollarr.story_manager import StoryManager
from scrollarr.database import Story, Chapter
from scrollarr.ebook_builder import EbookBuilder

class TestImageProcessing(unittest.TestCase):

    @patch('scrollarr.story_manager.init_db')
    @patch('scrollarr.story_manager.SessionLocal')
    @patch('scrollarr.story_manager.requests.get')
    @patch('scrollarr.story_manager.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    @patch('os.makedirs')
    @patch('scrollarr.story_manager.pkgutil.iter_modules')
    def test_download_images(self, mock_iter_modules, mock_makedirs, mock_exists, mock_file, mock_get, mock_session_cls, mock_init_db):
        # Prevent provider discovery from running actual imports
        mock_iter_modules.return_value = []

        # Setup DB mocks
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        story = MagicMock(spec=Story)
        story.id = 1
        story.title = "Test Story"
        story.source_url = "http://example.com/story"
        story.provider_name = "mock_provider"
        story.chapters = []

        chapter = MagicMock(spec=Chapter)
        chapter.id = 101
        chapter.title = "Chapter 1"
        chapter.source_url = "http://example.com/chap1"
        chapter.is_downloaded = False
        chapter.story_id = 1
        chapter.local_path = None

        # Mock query results
        # When querying Story
        mock_session.query.return_value.filter.return_value.first.return_value = story
        # When querying missing chapters
        mock_session.query.return_value.filter.return_value.all.return_value = [chapter]

        # Setup Manager
        # We need to mock internal components that might fail
        with patch('scrollarr.story_manager.SourceManager') as MockSourceManager:
             manager = StoryManager()

        # Mock Provider
        mock_provider = MagicMock()
        mock_provider.get_chapter_content.return_value = '<html><body><p>Text</p><img src="http://example.com/image.jpg"/></body></html>'

        # Inject provider into manager
        manager.source_manager.get_provider_for_url.return_value = mock_provider

        # Mock paths
        # Assume library root is /tmp/lib
        story_path = Path("/tmp/lib/Test Story (1)")
        chapter_path = story_path / "chapters/1.html"
        images_dir = story_path / "images"

        manager.library_manager.get_chapter_absolute_path = MagicMock(return_value=chapter_path)
        manager.library_manager.get_images_dir = MagicMock(return_value=images_dir)
        manager.library_manager.ensure_directories = MagicMock()

        # Mock exists:
        # Logic:
        # 1. `local_img_path.exists()` check 1 (should be False to trigger download)
        # 2. `local_img_path.exists()` check 2 (should be True to trigger update)
        # We use side_effect on the mock_exists instance
        mock_exists.side_effect = [False, True]

        # Mock requests
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'fake_image_data'
        mock_get.return_value = mock_resp

        # Run
        manager.download_missing_chapters(1)

        # Verify download
        mock_get.assert_called_with("http://example.com/image.jpg", timeout=10, headers={'User-Agent': 'Mozilla/5.0'})

        # Verify file write (image)
        handle = mock_file()
        handle.write.assert_any_call(b'fake_image_data')

        # Verify HTML update
        # We expect one of the write calls to contain the modified HTML
        write_calls = handle.write.call_args_list
        html_written = False
        for call in write_calls:
            args, _ = call
            content = args[0]
            if isinstance(content, str) and '<img' in content:
                # Calculate expected relative path
                # from /tmp/lib/Test Story (1)/chapters/1.html (parent is chapters)
                # to /tmp/lib/Test Story (1)/images/img_...
                # Path is ../images/img_...
                if 'src="../images/img_' in content:
                    html_written = True
                    # Also verify ext is jpg
                    self.assertIn('.jpg', content)
                    break

        self.assertTrue(html_written, "HTML content was not updated with local image path")

    @patch('scrollarr.ebook_builder.epub')
    @patch('scrollarr.ebook_builder.open', new_callable=mock_open)
    @patch('os.path.exists') # Patch os.path.exists used in _compile_chapters
    @patch('pathlib.Path.exists') # Patch pathlib.Path.exists used for image check
    def test_compile_chapters_images(self, mock_path_exists, mock_os_exists, mock_file, mock_epub):
        builder = EbookBuilder()
        builder.library_manager = MagicMock()
        builder.library_manager.get_compiled_absolute_path.return_value = Path("/tmp/out.epub")
        builder.library_manager.ensure_directories = MagicMock()

        story = MagicMock(spec=Story)
        story.title = "Test Story"
        story.profile = MagicMock()
        story.profile.output_format = 'epub'

        chapter = MagicMock(spec=Chapter)
        chapter.title = "Chapter 1"
        chapter.local_path = "/tmp/lib/Test Story/chapters/1.html"

        # Mock file content with relative image path
        # Content has <img src="../images/img_1.jpg"/>
        content = '<html><body><img src="../images/img_1.jpg"/></body></html>'
        mock_file.return_value.read.return_value = content

        # Mock os.path.exists to return True for chapter file
        mock_os_exists.return_value = True

        # Mock pathlib.Path.exists to return True for image file
        mock_path_exists.return_value = True

        # The tricky part: Path(chapter.local_path).parent / src
        # We need this to resolve to our expected absolute path
        # Since we mocked open, the file doesn't need to exist on disk.
        # But `_compile_chapters` calls `resolve()` on the path.

        # Let's patch `pathlib.Path.resolve` inside the context manager
        with patch('pathlib.Path.resolve') as mock_resolve:
            abs_img_path = Path("/tmp/lib/Test Story/images/img_1.jpg")
            mock_resolve.return_value = abs_img_path

            # We need to mock make_epub to verify it receives images
            builder.make_epub = MagicMock()

            # Run
            builder._compile_chapters(story, [chapter], "Full")

            # Verify make_epub called with images list
            builder.make_epub.assert_called()
            call_args = builder.make_epub.call_args
            # make_epub(title, author, epub_chapters, output_path, cover_path, css, images=...)
            # We can check kwargs
            kwargs = call_args[1]
            if 'images' in kwargs:
                self.assertEqual(kwargs['images'], [str(abs_img_path)])
            else:
                # Might be positional?
                # def make_epub(self, title, author, chapters, output_path, cover_path=None, css=None, images=None):
                # position 6 (0-indexed)
                if len(call_args[0]) >= 7:
                    self.assertEqual(call_args[0][6], [str(abs_img_path)])
                else:
                    self.fail("images argument not found in make_epub call")

            # Verify content passed to make_epub has updated src
            # args[2] is chapters
            chapters_arg = call_args[0][2]
            self.assertEqual(len(chapters_arg), 1)
            content_out = chapters_arg[0]['content']
            self.assertIn('src="images/img_1.jpg"', content_out)

if __name__ == '__main__':
    unittest.main()
