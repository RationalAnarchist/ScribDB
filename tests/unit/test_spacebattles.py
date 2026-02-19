import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrollarr.sources.spacebattles import SpaceBattlesSource

class TestSpaceBattlesSource(unittest.TestCase):
    def setUp(self):
        self.source = SpaceBattlesSource()

    def test_identify(self):
        # Valid URLs
        self.assertTrue(self.source.identify("https://forums.spacebattles.com/threads/story-title.12345/"))
        self.assertTrue(self.source.identify("https://forums.spacebattles.com/threads/story-title.12345/page-2"))

        # Invalid URLs
        self.assertFalse(self.source.identify("https://forum.questionablequesting.com/threads/story.123/"))
        self.assertFalse(self.source.identify("https://google.com"))

    def test_normalize_url(self):
        # Base URL
        url = "https://forums.spacebattles.com/threads/story-title.12345/"
        self.assertEqual(self.source._normalize_url(url), url)

        # URL with page
        url_page = "https://forums.spacebattles.com/threads/story-title.12345/page-2"
        self.assertEqual(self.source._normalize_url(url_page), url)

        # URL with threadmarks RSS
        url_rss = "https://forums.spacebattles.com/threads/story-title.12345/threadmarks.rss"
        self.assertEqual(self.source._normalize_url(url_rss), url)

        # URL without trailing slash (if regex supports it)
        url_no_slash = "https://forums.spacebattles.com/threads/story-title.12345"
        # The regex expects a dot followed by digits.
        # let's check regex: r'(https?://forums\.spacebattles\.com/threads/[^/]+\.\d+)'
        # It captures up to the digits. It adds a slash in return.
        self.assertEqual(self.source._normalize_url(url_no_slash), url)

if __name__ == '__main__':
    unittest.main()
