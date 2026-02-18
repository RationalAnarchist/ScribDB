import os
import sys
import unittest
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrollarr.ebook_builder import EbookBuilder

class TestEbookBuilder(unittest.TestCase):
    def setUp(self):
        self.output_path = "test_story.epub"
        self.builder = EbookBuilder()

    def tearDown(self):
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

    def test_make_epub(self):
        title = "Test Story"
        author = "Test Author"
        chapters = [
            {'title': 'Chapter 1: The Beginning', 'content': '<p>This is the first paragraph.</p>'},
            {'title': 'Chapter 2: The Middle', 'content': '<p>This is the second paragraph.</p>'},
            {'title': 'Chapter 3: The End', 'content': '<p>This is the final paragraph.</p>'}
        ]

        self.builder.make_epub(title, author, chapters, self.output_path)

        self.assertTrue(os.path.exists(self.output_path))
        print(f"Verified {self.output_path} exists.")

if __name__ == '__main__':
    unittest.main()
