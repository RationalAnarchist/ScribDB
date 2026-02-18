import unittest
from unittest.mock import MagicMock, patch
from scrollarr.sources.kemono import KemonoSource
from datetime import datetime

class TestKemonoSourceSearch(unittest.TestCase):
    def setUp(self):
        self.kemono = KemonoSource()

    @patch('playwright.sync_api.sync_playwright')
    def test_search(self, mock_sync_playwright):
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
                <div class="card-list__items">
                    <a href="/service/user/123">
                        <div class="user-card__header" style="background-image: url('/icon.jpg')"></div>
                        <div class="user-card__name">Artist Name</div>
                        <div class="user-card__service">Patreon</div>
                    </a>
                </div>
            </body>
        </html>
        """
        mock_page.content.return_value = html

        results = self.kemono.search("test")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "Artist Name")
        self.assertEqual(results[0]['url'], "https://kemono.cr/service/user/123")
        self.assertEqual(results[0]['author'], "Patreon")
        self.assertEqual(results[0]['cover_url'], "https://kemono.cr/icon.jpg")

if __name__ == '__main__':
    unittest.main()
