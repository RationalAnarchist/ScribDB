import unittest
from unittest.mock import MagicMock, patch
from scrollarr.sources.kemono import KemonoSource
import subprocess

class TestKemonoInstall(unittest.TestCase):
    def setUp(self):
        self.kemono = KemonoSource()

    @patch('subprocess.run')
    @patch('playwright.sync_api.sync_playwright')
    def test_auto_install_browser(self, mock_sync_playwright, mock_subprocess_run):
        # Setup mocks
        mock_playwright_context_manager = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value = mock_playwright_context_manager
        mock_playwright_context_manager.__enter__.return_value = mock_playwright

        # Configure launch to fail first time, succeed second time
        exception = Exception("Executable doesn't exist at /path/to/chrome")
        mock_playwright.chromium.launch.side_effect = [exception, mock_browser]

        mock_browser.new_page.return_value = mock_page
        mock_page.content.return_value = "<html></html>"

        # Call a method that triggers scrape
        self.kemono._scrape_page("https://example.com")

        # Verify install was called
        mock_subprocess_run.assert_called_with(["playwright", "install", "chromium"], check=True)

        # Verify launch was called twice
        self.assertEqual(mock_playwright.chromium.launch.call_count, 2)

if __name__ == '__main__':
    unittest.main()
