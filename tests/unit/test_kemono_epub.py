import unittest
from unittest.mock import MagicMock, patch
from scrollarr.sources.kemono import KemonoSource
import ebooklib
from ebooklib import epub
import os
import tempfile

class TestKemonoEpub(unittest.TestCase):
    def setUp(self):
        self.kemono = KemonoSource()
        self.tmp_epub_path = tempfile.mktemp(suffix=".epub")
        self._create_dummy_epub(self.tmp_epub_path)

    def tearDown(self):
        if os.path.exists(self.tmp_epub_path):
            os.remove(self.tmp_epub_path)

    def _create_dummy_epub(self, path):
        book = epub.EpubBook()
        book.set_identifier('id123456')
        book.set_title('Sample Book')
        book.set_language('en')
        book.add_author('Author Name')

        c1 = epub.EpubHtml(title='Intro', file_name='intro.xhtml', lang='en')
        c1.content = '<h1>Intro</h1><p>Epub Content.</p>'
        book.add_item(c1)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        book.spine = ['nav', c1]
        epub.write_epub(path, book, {})

    def test_extract_epub_content(self):
        content = self.kemono._extract_epub_content(self.tmp_epub_path)
        self.assertIn("Epub Content.", content)
        self.assertIn("<h1>Intro</h1>", content)

    @patch('playwright.sync_api.sync_playwright')
    def test_get_chapter_content_merging(self, mock_sync_playwright):
        # Create temp file mock return values BEFORE patching tempfile
        fd, _ = tempfile.mkstemp()
        # os.close(fd) <-- REMOVED: Let the code close it

        with patch('tempfile.mkstemp') as mock_mkstemp:
            mock_mkstemp.return_value = (fd, self.tmp_epub_path)

            mock_playwright_context_manager = MagicMock(name="CM")
            mock_playwright = MagicMock(name="Playwright")
            mock_browser = MagicMock(name="Browser")
            mock_page = MagicMock(name="Page")

            mock_sync_playwright.return_value = mock_playwright_context_manager
            mock_playwright_context_manager.__enter__.return_value = mock_playwright
            mock_playwright.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            # Setup DOM mocks
            mock_content = MagicMock(name="Content")
            mock_content.inner_html.return_value = "" # Empty content

            mock_att = MagicMock(name="Attachment")

            def get_attr_side_effect(name):
                if name == 'href': return "book.epub"
                return None
            mock_att.get_attribute.side_effect = get_attr_side_effect

            mock_att.click = MagicMock()

            # Important: Ensure query_selector on attachment (checking for thumb) returns None
            mock_att.query_selector.return_value = None

            def query_selector_side_effect(selector):
                if selector == '.post__content': return mock_content
                return None

            mock_page.query_selector.side_effect = query_selector_side_effect

            mock_page.query_selector_all.return_value = [mock_att]

            # Mock download
            mock_download = MagicMock(name="Download")
            mock_download.save_as = MagicMock()
            mock_page.expect_download.return_value.__enter__.return_value.value = mock_download

            content = self.kemono.get_chapter_content("http://url")

            # print(f"DEBUG CONTENT: {content}")

            self.assertIn("Epub Content", content)
            self.assertNotIn("<hr/>", content)

if __name__ == '__main__':
    unittest.main()
