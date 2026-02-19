import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from scrollarr.sources.scribblehub import ScribbleHubSource

class TestScribbleHubSource(unittest.TestCase):
    def setUp(self):
        self.sh = ScribbleHubSource()

    def test_identify(self):
        self.assertTrue(self.sh.identify("https://www.scribblehub.com/series/123/title/"))
        self.assertFalse(self.sh.identify("https://royalroad.com"))

    @patch('scrollarr.sources.scribblehub.ScribbleHubSource._get_playwright')
    def test_get_metadata(self, mock_get_playwright):
        # Setup mocks
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_p
        mock_get_playwright.return_value = mock_context

        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # HTML Content
        html = """
        <html>
            <body>
                <div class="fic_title">My Story</div>
                <span class="auth_name_fic">The Author</span>
                <div class="fic_description">This is a description.</div>
                <div class="fic_image"><img src="https://example.com/cover.jpg"></div>
                <span class="wi_fic_showtags">
                    <a class="stag">Tag1</a>
                    <a class="stag">Tag2</a>
                </span>
            </body>
        </html>
        """
        mock_page.content.return_value = html

        meta = self.sh.get_metadata("https://www.scribblehub.com/series/123/")

        self.assertEqual(meta['title'], "My Story")
        self.assertEqual(meta['author'], "The Author")
        self.assertIn("This is a description", meta['description'])
        self.assertEqual(meta['cover_url'], "https://example.com/cover.jpg")
        self.assertIn("Tag1", meta['tags'])
        self.assertIn("Tag2", meta['tags'])

    @patch('scrollarr.sources.scribblehub.ScribbleHubSource._get_playwright')
    def test_get_chapter_list_pagination(self, mock_get_playwright):
        # Setup mocks
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_p
        mock_get_playwright.return_value = mock_context

        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Page 1 HTML
        page1 = """
        <html>
            <body>
                <li class="toc_w">
                    <a class="toc_a" href="https://sh.com/ch2">Chapter 2</a>
                    <span class="fic_date_pub" title="Jan 02, 2023 10:00 AM">Jan 02</span>
                </li>
                <a class="page-link next" href="?toc=2">Next</a>
            </body>
        </html>
        """
        # Page 2 HTML
        page2 = """
        <html>
            <body>
                <li class="toc_w">
                    <a class="toc_a" href="https://sh.com/ch1">Chapter 1</a>
                    <span class="fic_date_pub" title="Jan 01, 2023 10:00 AM">Jan 01</span>
                </li>
                <!-- No Next Link -->
            </body>
        </html>
        """

        mock_page.content.side_effect = [page1, page2]
        # Mock URL property for loop check
        mock_page.url = "https://sh.com/series/123/"

        chapters = self.sh.get_chapter_list("https://sh.com/series/123/")

        # Should have 2 chapters
        self.assertEqual(len(chapters), 2)
        # Check order (reversed in implementation to be oldest first)
        self.assertEqual(chapters[0]['title'], "Chapter 1")
        self.assertEqual(chapters[1]['title'], "Chapter 2")

        self.assertEqual(chapters[0]['published_date'].day, 1)
        self.assertEqual(chapters[1]['published_date'].day, 2)

    @patch('scrollarr.sources.scribblehub.ScribbleHubSource._get_playwright')
    def test_get_chapter_content(self, mock_get_playwright):
        # Setup mocks
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_p
        mock_get_playwright.return_value = mock_context

        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        html = """
        <html>
            <body>
                <div id="chp_raw">
                    <p>Story text.</p>
                    <script>var x=1;</script>
                </div>
            </body>
        </html>
        """
        mock_page.content.return_value = html

        content = self.sh.get_chapter_content("https://sh.com/ch1")

        self.assertIn("<p>Story text.</p>", content)
        self.assertNotIn("<script>", content)

    @patch('scrollarr.sources.scribblehub.ScribbleHubSource._get_playwright')
    def test_search(self, mock_get_playwright):
        # Setup mocks
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_p
        mock_get_playwright.return_value = mock_context

        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        html = """
        <html>
            <body>
                <div class="search_main_box">
                    <div class="search_title"><a href="https://sh.com/s1">Story 1</a></div>
                    <div class="search_img"><img src="cov1.jpg"></div>
                    <span title="Author"><a href="#">Author 1</a></span>
                </div>
            </body>
        </html>
        """
        mock_page.content.return_value = html

        results = self.sh.search("query")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "Story 1")
        self.assertEqual(results[0]['author'], "Author 1")
        self.assertEqual(results[0]['cover_url'], "cov1.jpg")

if __name__ == '__main__':
    unittest.main()
