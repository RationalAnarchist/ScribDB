import unittest
from unittest.mock import MagicMock
from ao3 import AO3Source
from bs4 import BeautifulSoup

class TestAO3Source(unittest.TestCase):
    def setUp(self):
        self.ao3 = AO3Source()
        self.ao3.requester.get = MagicMock()

    def test_identify(self):
        self.assertTrue(self.ao3.identify("https://archiveofourown.org/works/123"))
        self.assertFalse(self.ao3.identify("https://www.royalroad.com/fiction/123"))

    def test_get_metadata(self):
        html = """
        <html>
            <body>
                <div id="workskin">
                    <div class="preface group">
                        <h2 class="title heading">My Awesome Story</h2>
                        <h3 class="byline heading"><a href="/users/testuser">testuser</a></h3>
                        <blockquote class="userstuff summary">
                            <p>This is a summary.</p>
                        </blockquote>
                        <dl class="tags">
                            <dt class="rating tags">Rating:</dt>
                            <dd class="rating tags">
                                <ul class="commas">
                                    <li><a class="tag" href="/tags/General%20Audiences">General Audiences</a></li>
                                </ul>
                            </dd>
                            <dt class="language">Language:</dt>
                            <dd class="language">English</dd>
                            <dt class="fandom tags">Fandoms:</dt>
                            <dd class="fandom tags">
                                <ul class="commas">
                                    <li><a class="tag" href="/tags/Harry%20Potter">Harry Potter</a></li>
                                </ul>
                            </dd>
                            <dt class="freeform tags">Additional Tags:</dt>
                            <dd class="freeform tags">
                                <ul class="commas">
                                    <li><a class="tag" href="/tags/Magic">Magic</a></li>
                                    <li><a class="tag" href="/tags/Adventure">Adventure</a></li>
                                </ul>
                            </dd>
                            <dt class="stats">Stats:</dt>
                            <dd class="stats">
                                <dl class="stats">
                                    <dt class="status">Status:</dt>
                                    <dd class="status">Completed</dd>
                                    <dt class="chapters">Chapters:</dt>
                                    <dd class="chapters">10/10</dd>
                                </dl>
                            </dd>
                        </dl>
                    </div>
                </div>
            </body>
        </html>
        """
        self.ao3.requester.get.return_value = MagicMock(text=html)
        metadata = self.ao3.get_metadata("https://archiveofourown.org/works/123")

        self.assertEqual(metadata['title'], "My Awesome Story")
        self.assertEqual(metadata['author'], "testuser")
        self.assertIn("This is a summary.", metadata['description'])
        self.assertEqual(metadata['rating'], "General Audiences")
        self.assertEqual(metadata['language'], "English")
        self.assertIn("Harry Potter", metadata['tags'])
        self.assertIn("Magic", metadata['tags'])
        self.assertEqual(metadata['publication_status'], "Completed")

    def test_get_chapter_list_multi(self):
        # Mock navigate page
        html = """
        <html>
            <body>
                <ol class="chapter index group">
                    <li>
                        <a href="/works/123/chapters/1">Chapter 1</a>
                        <span class="datetime">(2023-01-01)</span>
                    </li>
                    <li>
                        <a href="/works/123/chapters/2">Chapter 2</a>
                        <span class="datetime">(2023-01-02)</span>
                    </li>
                </ol>
            </body>
        </html>
        """
        self.ao3.requester.get.return_value.text = html
        chapters = self.ao3.get_chapter_list("https://archiveofourown.org/works/123")

        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0]['title'], "Chapter 1")
        self.assertEqual(chapters[0]['url'], "https://archiveofourown.org/works/123/chapters/1")
        self.assertEqual(chapters[0]['published_date'].strftime('%Y-%m-%d'), '2023-01-01')
        self.assertEqual(chapters[1]['published_date'].strftime('%Y-%m-%d'), '2023-01-02')

    def test_get_chapter_list_single(self):
        # Mock navigate page returning nothing (or empty list)

        def side_effect(url):
            mock_resp = MagicMock()
            if "navigate" in url:
                mock_resp.text = "<html><body></body></html>"
            else:
                mock_resp.text = """
                <html>
                    <body>
                        <h2 class="title heading">Single Chapter Story</h2>
                        <div id="chapters" class="userstuff">Content</div>
                    </h2>
                </body>
                </html>
                """
            return mock_resp

        self.ao3.requester.get.side_effect = side_effect

        chapters = self.ao3.get_chapter_list("https://archiveofourown.org/works/456")

        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0]['title'], "Single Chapter Story")
        self.assertEqual(chapters[0]['url'], "https://archiveofourown.org/works/456")

    def test_get_chapter_content(self):
        html = """
        <html>
            <body>
                <div id="chapters" class="userstuff">
                    <h3 class="landmark heading">Chapter Text</h3>
                    <p>This is the chapter content.</p>
                </div>
            </body>
        </html>
        """
        # Reset side effect
        self.ao3.requester.get.side_effect = None
        self.ao3.requester.get.return_value.text = html

        content = self.ao3.get_chapter_content("https://archiveofourown.org/works/123/chapters/1")

        self.assertIn("This is the chapter content.", content)
        self.assertNotIn("Chapter Text", content)

if __name__ == '__main__':
    unittest.main()
