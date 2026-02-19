import unittest
from unittest.mock import MagicMock, patch
from scrollarr.sources.kemono import KemonoSource
from datetime import datetime

class TestKemonoSource(unittest.TestCase):
    def setUp(self):
        self.kemono = KemonoSource()

    def test_identify(self):
        self.assertTrue(self.kemono.identify("https://kemono.su/fanbox/user/123"))
        self.assertTrue(self.kemono.identify("https://kemono.party/patreon/user/456"))
        self.assertFalse(self.kemono.identify("https://google.com"))

    @patch('playwright.sync_api.sync_playwright')
    def test_get_metadata(self, mock_sync_playwright):
        # Mock context manager
        mock_playwright_context_manager = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value = mock_playwright_context_manager
        mock_playwright_context_manager.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        html = """
        <html>
            <body>
                <h1 class="user-header__name"><span>Test Artist</span></h1>
                <div class="user-header__avatar"><img src="/icons/user/123.jpg"></div>
            </body>
        </html>
        """
        mock_page.content.return_value = html

        metadata = self.kemono.get_metadata("https://kemono.su/fanbox/user/123")

        self.assertEqual(metadata['title'], "Test Artist")
        self.assertEqual(metadata['author'], "Test Artist")
        self.assertEqual(metadata['cover_url'], "https://kemono.su/icons/user/123.jpg")

    @patch('playwright.sync_api.sync_playwright')
    def test_get_chapter_list(self, mock_sync_playwright):
        mock_playwright_context_manager = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value = mock_playwright_context_manager
        mock_playwright_context_manager.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # Mock HTML for list page
        html = """
        <html>
            <body>
                <div class="card-list__items">
                    <article class="post-card">
                        <a href="/fanbox/user/123/post/100">
                            <header class="post-card__header">Post 1</header>
                            <div class="post-card__footer">
                                <div>Published: 2023-01-01 12:00:00</div>
                            </div>
                        </a>
                    </article>
                     <article class="post-card">
                        <a href="/fanbox/user/123/post/101">
                            <header class="post-card__header">Post 2</header>
                            <div class="post-card__footer">
                                <div>Published: 2023-01-02</div>
                            </div>
                        </a>
                    </article>
                </div>
            </body>
        </html>
        """
        html_empty = """<html><body><div class="card-list__items"></div></body></html>"""

        # First call returns html, second call (next page) returns empty list HTML
        mock_page.content.side_effect = [html, html_empty]

        chapters = self.kemono.get_chapter_list("https://kemono.su/fanbox/user/123")

        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0]['title'], "Post 1")
        self.assertEqual(chapters[0]['url'], "https://kemono.su/fanbox/user/123/post/100")

        # Check if date is parsed correctly
        # Note: In my implementation, I strip "Published:" and parse.
        # "2023-01-01 12:00:00" -> datetime object
        self.assertIsInstance(chapters[0]['published_date'], datetime)
        self.assertEqual(chapters[0]['published_date'].year, 2023)

    @patch('playwright.sync_api.sync_playwright')
    def test_get_chapter_content(self, mock_sync_playwright):
        mock_playwright_context_manager = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value = mock_playwright_context_manager
        mock_playwright_context_manager.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Mock query_selector
        mock_element = MagicMock()
        mock_element.inner_html.return_value = "<p>Content</p>"

        def query_selector_side_effect(selector):
            if selector == '.post__content':
                return mock_element
            if selector == '.post-content':
                return None
            if selector == '.post__thumbnail img':
                return None
            return None

        mock_page.query_selector.side_effect = query_selector_side_effect
        mock_page.query_selector_all.return_value = []

        content = self.kemono.get_chapter_content("https://kemono.su/post/1")
        self.assertIn("<p>Content</p>", content)

if __name__ == '__main__':
    unittest.main()
