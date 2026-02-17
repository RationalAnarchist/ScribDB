import unittest
import sys
import os
from unittest.mock import MagicMock
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sources.royalroad import RoyalRoadSource
import json

class TestRoyalRoadSource(unittest.TestCase):
    def setUp(self):
        self.rr = RoyalRoadSource()
        self.rr.requester.get = MagicMock()

    def test_get_metadata(self):
        html = """
        <html>
            <body>
                <div class="fiction-header">
                    <h1>My RR Story</h1>
                    <h4>
                        <span class="small">by </span>
                        <span>
                            <a href="/profile/123">The Author</a>
                        </span>
                    </h4>
                </div>
                <div class="description">
                    <div class="hidden-content">
                        <p>This is the synopsis.</p>
                    </div>
                </div>
                <div class="fiction-info">
                    <span class="label label-default label-sm bg-blue-hoki">ONGOING</span>
                    <span class="tags">
                        <span class="fiction-tag">LitRPG</span>
                        <span class="fiction-tag">Fantasy</span>
                    </span>
                </div>
                <script type="application/ld+json">
                {
                    "@context": "https://schema.org",
                    "@type": "Book",
                    "name": "My RR Story",
                    "aggregateRating": {
                        "@type": "AggregateRating",
                        "ratingValue": 4.5
                    },
                    "genre": ["LitRPG", "Fantasy"]
                }
                </script>
            </body>
        </html>
        """
        self.rr.requester.get.return_value = MagicMock(text=html)
        metadata = self.rr.get_metadata("https://www.royalroad.com/fiction/123")

        self.assertEqual(metadata['title'], "My RR Story")
        self.assertEqual(metadata['author'], "The Author")
        self.assertIn("This is the synopsis.", metadata['description'])
        self.assertEqual(metadata['rating'], "4.5")
        self.assertIn("LitRPG", metadata['tags'])
        self.assertIn("Fantasy", metadata['tags'])
        self.assertEqual(metadata['publication_status'], "Ongoing")

    def test_get_chapter_list(self):
        html = """
        <html>
            <body>
                <table id="chapters">
                    <tr class="chapter-row">
                        <td><a href="/fiction/123/chapter/1">Chapter 1: The Beginning</a></td>
                        <td><time datetime="2023-01-01T12:00:00Z">Jan 01, 2023</time></td>
                    </tr>
                    <tr class="chapter-row">
                        <td><a href="/fiction/123/chapter/2">Chapter 2: The End</a></td>
                        <!-- No date test case -->
                    </tr>
                </table>
            </body>
        </html>
        """
        self.rr.requester.get.return_value.text = html
        chapters = self.rr.get_chapter_list("http://example.com")

        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0]['title'], "Chapter 1: The Beginning")
        self.assertEqual(chapters[0]['url'], "https://www.royalroad.com/fiction/123/chapter/1")
        self.assertEqual(chapters[0]['published_date'].strftime('%Y-%m-%d'), '2023-01-01')
        self.assertEqual(chapters[1]['title'], "Chapter 2: The End")
        self.assertIsNone(chapters[1]['published_date'])

    def test_get_chapter_content_removes_unwanted(self):
        html = """
        <html>
            <body>
                <div class="chapter-inner chapter-content">
                    <p>This is the story content.</p>

                    <div class="nav-buttons">
                        <a href="/prev">Previous Chapter</a>
                        <a href="/next">Next Chapter</a>
                    </div>

                    <div class="portlet">
                        <p>Support the Author on Patreon!</p>
                    </div>

                    <p>Some more story content.</p>

                    <p>Donate to me!</p>
                </div>
            </body>
        </html>
        """
        self.rr.requester.get.return_value.text = html
        content = self.rr.get_chapter_content("http://example.com/chapter/1")

        # Check that story content is present
        self.assertIn("This is the story content.", content)
        self.assertIn("Some more story content.", content)

        # Check that unwanted content IS NOT present (after fix)
        self.assertNotIn("Next Chapter", content, "Should not contain 'Next Chapter'")
        self.assertNotIn("Previous Chapter", content, "Should not contain 'Previous Chapter'")
        self.assertNotIn("Support the Author", content, "Should not contain 'Support the Author'")
        self.assertNotIn("Donate", content, "Should not contain 'Donate' (as independent text)")

    def test_get_chapter_content_preserves_dialogue(self):
        html = """
        <html>
            <body>
                <div class="chapter-inner chapter-content">
                    <p>"I will not Donate to their cause," he said.</p>
                    <p>She replied, "Support the Author? No way."</p>
                </div>
            </body>
        </html>
        """
        self.rr.requester.get.return_value.text = html
        content = self.rr.get_chapter_content("http://example.com/chapter/2")

        # Should still be present because it's part of a longer sentence/dialogue
        self.assertIn("Donate", content)
        self.assertIn("Support the Author", content)

    def test_get_chapter_content_removes_portlet_partial_match(self):
        html = """
        <html>
            <body>
                <div class="chapter-inner chapter-content">
                    <p>Story content.</p>
                    <div class="author-note-portlet">
                        <p>This is an author note.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        self.rr.requester.get.return_value.text = html
        content = self.rr.get_chapter_content("http://example.com/chapter/3")

        self.assertNotIn("author note", content)

if __name__ == '__main__':
    unittest.main()
