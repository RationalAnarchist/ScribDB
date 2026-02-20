import unittest
from unittest.mock import MagicMock, patch
from scrollarr.sources.kemono import KemonoSource
from datetime import datetime

class TestKemonoTags(unittest.TestCase):
    def setUp(self):
        self.kemono = KemonoSource()

    @patch('playwright.sync_api.sync_playwright')
    def test_get_chapter_list_with_tags(self, mock_sync_playwright):
        # Mock Playwright setup
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

        # Mock HTML with tags
        html = """
        <html>
            <body>
                <div class="card-list__items">
                    <article class="post-card">
                        <a href="/fanbox/user/123/post/100">
                            <header class="post-card__header">Post with Tags</header>
                            <div class="post-card__footer">
                                <div>Published: 2023-01-01</div>
                            </div>
                            <div class="post-card__tags">
                                <a href="/fanbox/user/123/tag/Tag1">Tag1</a>
                                <a href="/fanbox/user/123/tag/Tag 2">Tag 2</a>
                            </div>
                        </a>
                    </article>
                    <article class="post-card">
                        <a href="/fanbox/user/123/post/101">
                            <header class="post-card__header">Post without Tags</header>
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

        # Check first chapter
        self.assertEqual(chapters[0]['title'], "Post with Tags")
        self.assertIn('tags', chapters[0])
        self.assertEqual(chapters[0]['tags'], ['Tag1', 'Tag 2'])

        # Check second chapter
        self.assertEqual(chapters[1]['title'], "Post without Tags")
        self.assertIn('tags', chapters[1])
        self.assertEqual(chapters[1]['tags'], [])

if __name__ == '__main__':
    unittest.main()
