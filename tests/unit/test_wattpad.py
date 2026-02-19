import unittest
from unittest.mock import MagicMock, patch
from scrollarr.sources.wattpad import WattpadSource

class TestWattpadSource(unittest.TestCase):
    def setUp(self):
        self.source = WattpadSource()

    def test_identify(self):
        self.assertTrue(self.source.identify("https://www.wattpad.com/story/123"))
        self.assertFalse(self.source.identify("https://google.com"))

    @patch('playwright.sync_api.sync_playwright')
    def test_get_metadata(self, mock_sync_playwright):
        # Mock Context
        mock_context_manager = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value = mock_context_manager
        mock_context_manager.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        html = """
        <html>
            <body>
                <h1>Test Story Title</h1>
                <a href="/user/testauthor">testauthor</a>
                <div class="description">This is a test description.</div>
                <ul class="tag-items">
                    <li><a href="/tags/romance">Romance</a></li>
                </ul>
            </body>
        </html>
        """
        mock_page.content.return_value = html

        # Need to mock query_selector_all because get_metadata logic might use it
        # Actually get_metadata uses BS4 mostly, but let's see.

        metadata = self.source.get_metadata("https://www.wattpad.com/story/123")

        self.assertEqual(metadata['title'], "Test Story Title")
        self.assertEqual(metadata['author'], "testauthor")
        self.assertEqual(metadata['description'], "This is a test description.")
        self.assertEqual(metadata['tags'], "Romance")

    @patch('playwright.sync_api.sync_playwright')
    def test_get_chapter_list(self, mock_sync_playwright):
        mock_context_manager = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value = mock_context_manager
        mock_context_manager.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Mock evaluate result for hrefs
        links = [
            {'href': 'https://www.wattpad.com', 'text': 'Home'},
            {'href': '/story/123', 'text': 'Story Link'},
            {'href': '/user/testauthor', 'text': 'Author'},
            {'href': '/1001-chapter-one', 'text': 'Chapter One'},
            {'href': '/1002-chapter-two', 'text': 'Chapter Two'},
            {'href': 'https://www.wattpad.com/1003-chapter-three', 'text': 'Chapter Three'},
            {'href': '/list/123', 'text': 'Reading List'}
        ]
        mock_page.evaluate.return_value = links

        chapters = self.source.get_chapter_list("https://www.wattpad.com/story/123")

        # Should filter out non-chapter links
        # Should keep /1001-, /1002-, /1003-
        # Verify length
        # My implementation logic:
        # regex = re.compile(r'^/?(\d+)-.+$')
        # /1001-chapter-one -> matches
        # /1002-chapter-two -> matches
        # https://www.wattpad.com/1003-chapter-three -> filtered by 'wattpad.com' check but regex matching on full URL might fail if not handled?
        # Let's check logic:
        # if 'wattpad.com' in href:
        #   match = re.search(r'wattpad\.com/(\d+)-', href)
        #   if match: keep
        # So https://www.wattpad.com/1003-chapter-three should match.

        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[0]['title'], "Chapter One")
        self.assertEqual(chapters[0]['url'], "https://www.wattpad.com/1001-chapter-one")
        self.assertEqual(chapters[1]['title'], "Chapter Two")
        self.assertEqual(chapters[2]['title'], "Chapter Three")
        self.assertEqual(chapters[2]['url'], "https://www.wattpad.com/1003-chapter-three")

    @patch('playwright.sync_api.sync_playwright')
    def test_get_chapter_content(self, mock_sync_playwright):
        mock_context_manager = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value = mock_context_manager
        mock_context_manager.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        html = """
        <html>
            <body>
                <pre>This is the chapter content.</pre>
            </body>
        </html>
        """
        mock_page.content.return_value = html
        mock_page.evaluate.return_value = None

        content = self.source.get_chapter_content("https://www.wattpad.com/1001-chapter-one")
        self.assertIn("This is the chapter content.", content)

    @patch('playwright.sync_api.sync_playwright')
    def test_search(self, mock_sync_playwright):
        mock_context_manager = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_sync_playwright.return_value = mock_context_manager
        mock_context_manager.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Need to structure HTML so BS4 can parse it
        # .story-card link wrapping .story-card-data
        html = """
        <html>
            <body>
                <a class="story-card" href="/story/999-search-result">
                    <div class="story-card-data">
                        <div class="cover"><img src="cover.jpg"></div>
                        <div class="story-info">
                            <div class="title">Search Result Story</div>
                            <div class="username">search_author</div>
                        </div>
                        <div class="username">search_author_fallback</div>
                    </div>
                </a>
            </body>
        </html>
        """
        mock_page.content.return_value = html

        results = self.source.search("query")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "Search Result Story")
        # Depending on implementation, it might pick .username from inside story-info or outside
        # My implementation: user_div = card.select_one('.username')
        # If it finds one, good.
        self.assertEqual(results[0]['author'], "search_author")
        self.assertEqual(results[0]['url'], "https://www.wattpad.com/story/999-search-result")

if __name__ == '__main__':
    unittest.main()
