import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure we can import from scrollarr
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from scrollarr.ebook_builder import EbookBuilder

class TestEbookBuilderCleaning(unittest.TestCase):
    @patch('scrollarr.ebook_builder.LibraryManager')
    def setUp(self, mock_lib_manager):
        self.builder = EbookBuilder()

    def test_clean_html_content_basic(self):
        html = "<p>Text</p>"
        cleaned = self.builder._clean_html_content(html)
        self.assertIn("<p>Text</p>", cleaned)

    def test_clean_html_excessive_br(self):
        # <br> outside of p should be collapsed to single br
        html = "<p>P1</p><br><br><br><br><p>P2</p>"
        cleaned = self.builder._clean_html_content(html)
        # Regex (br){2,} -> br
        self.assertIn("<p>P1</p><br/><p>P2</p>", cleaned)
        self.assertNotIn("<br/><br/>", cleaned)

    def test_clean_html_empty_paragraphs(self):
        # Empty paragraphs should be removed entirely to rely on margins
        html = "<p>P1</p><p></p><p>&nbsp;</p><p>P2</p>"
        cleaned = self.builder._clean_html_content(html)
        # <p></p> -> Removed
        # <p>&nbsp;</p> -> Removed
        # Result: <p>P1</p><p>P2</p> (standard spacing)
        self.assertIn("<p>P1</p><p>P2</p>", cleaned)
        self.assertNotIn("<br/>", cleaned)

    def test_clean_html_mixed(self):
        html = "<p>P1</p><br><br><br><p>&nbsp;</p><p>P2</p>"
        # <br><br><br> -> <br/>
        # <p>&nbsp;</p> -> Removed
        # Result: <p>P1</p><br/><p>P2</p>
        cleaned = self.builder._clean_html_content(html)
        self.assertIn("<p>P1</p><br/><p>P2</p>", cleaned)
        self.assertNotIn("&nbsp;", cleaned)
        self.assertNotIn("<br/><br/>", cleaned)

    def test_clean_html_paragraph_br(self):
        # <p><br/></p> should be removed (it's a spacer)
        html = "<p>P1</p><p><br/></p><p><br/></p><p><br/></p><p>P2</p>"
        cleaned = self.builder._clean_html_content(html)
        # All <p><br/></p> removed
        # Result: <p>P1</p><p>P2</p>
        self.assertIn("<p>P1</p><p>P2</p>", cleaned)
        self.assertNotIn("<br/>", cleaned)

    def test_clean_html_empty_spans(self):
        # <p><span> </span></p> should be removed
        html = "<p>P1</p><p><span> </span></p><p><span>&nbsp;</span></p><p>P2</p>"
        cleaned = self.builder._clean_html_content(html)
        self.assertIn("<p>P1</p><p>P2</p>", cleaned)
        self.assertNotIn("<span> </span>", cleaned)

if __name__ == '__main__':
    unittest.main()
