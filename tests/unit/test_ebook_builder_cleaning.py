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
        html = "<p>P1</p><br><br><br><br><p>P2</p>"
        cleaned = self.builder._clean_html_content(html)
        # Expect max 2 <br/>
        # We check for exact sequence if possible, or absence of 3
        self.assertIn("<br/><br/>", cleaned)
        self.assertNotIn("<br/><br/><br/>", cleaned)

    def test_clean_html_empty_paragraphs(self):
        html = "<p>P1</p><p></p><p>&nbsp;</p><p>P2</p>"
        cleaned = self.builder._clean_html_content(html)
        # Empty paragraphs converted to <br/>, then normalized
        # <p></p> -> <br/>
        # <p>&nbsp;</p> -> <br/>
        # So we have <p>P1</p><br/><br/><p>P2</p>
        self.assertIn("<br/><br/>", cleaned)
        self.assertNotIn("<p></p>", cleaned)
        self.assertNotIn("<p>&nbsp;</p>", cleaned)

    def test_clean_html_mixed(self):
        html = "<p>P1</p><br><br><br><p>&nbsp;</p><p>P2</p>"
        # <br><br><br> -> <br/><br/><br/>
        # <p>&nbsp;</p> -> <br/>
        # Total 4 <br/>
        # Regex reduces to 2
        cleaned = self.builder._clean_html_content(html)
        self.assertIn("<br/><br/>", cleaned)
        self.assertNotIn("<br/><br/><br/>", cleaned)
        self.assertNotIn("&nbsp;", cleaned)

    def test_clean_html_paragraph_br(self):
        # <p><br/></p> should be treated as <br/>
        html = "<p>P1</p><p><br/></p><p><br/></p><p><br/></p><p>P2</p>"
        cleaned = self.builder._clean_html_content(html)
        # Should be converted to <br/> <br/> <br/> then reduced
        self.assertIn("<br/><br/>", cleaned)
        self.assertNotIn("<p><br/></p>", cleaned)
        self.assertNotIn("<br/><br/><br/>", cleaned)

    def test_clean_html_empty_spans(self):
        # <p><span> </span></p> should be treated as empty/br
        html = "<p>P1</p><p><span> </span></p><p><span>&nbsp;</span></p><p>P2</p>"
        cleaned = self.builder._clean_html_content(html)
        self.assertIn("<br/><br/>", cleaned)
        self.assertNotIn("<span> </span>", cleaned)
        self.assertNotIn("<span>&nbsp;</span>", cleaned)

if __name__ == '__main__':
    unittest.main()
