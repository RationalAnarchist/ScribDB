import unittest
from unittest.mock import MagicMock, patch
from scrollarr.sources.kemono import KemonoSource
from datetime import datetime

class TestKemonoAPI(unittest.TestCase):
    def setUp(self):
        self.kemono = KemonoSource()

    @patch('playwright.sync_api.sync_playwright')
    def test_get_chapter_list_api(self, mock_sync_playwright):
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

        # Mock API Responses via page.evaluate
        def mock_evaluate(script, *args):
            # If script calls fetch for tags
            if "/tags" in script:
                return [{'tag': 'Tag1', 'post_count': 10}, {'tag': 'Tag2', 'post_count': 5}]

            # If script calls Promise.all for tag mapping
            if "Promise.all" in script:
                # We return a map of Tag -> [PostIDs]
                return {
                    'Tag1': ['100', '101'],
                    'Tag2': ['100']
                }

            # If script calls fetch for posts (loop)
            if "/posts?o=0" in script:
                return [
                    {'id': '100', 'title': 'Post 1', 'published': '2023-01-01T12:00:00'},
                    {'id': '101', 'title': 'Post 2', 'published': '2023-01-02T12:00:00'}
                ]

            if "/posts?o=50" in script:
                return [] # End of list

            return None

        mock_page.evaluate.side_effect = mock_evaluate

        url = "https://kemono.cr/patreon/user/123"
        chapters = self.kemono.get_chapter_list(url)

        self.assertEqual(len(chapters), 2)

        # Check Post 1 (ID 100) -> Should have Tag1 and Tag2
        post1 = next(c for c in chapters if c['url'].endswith('/post/100'))
        self.assertEqual(post1['title'], "Post 1")
        self.assertIn('Tag1', post1['tags'])
        self.assertIn('Tag2', post1['tags'])

        # Check Post 2 (ID 101) -> Should have Tag1 only
        post2 = next(c for c in chapters if c['url'].endswith('/post/101'))
        self.assertEqual(post2['title'], "Post 2")
        self.assertEqual(post2['tags'], ['Tag1'])

if __name__ == '__main__':
    unittest.main()
