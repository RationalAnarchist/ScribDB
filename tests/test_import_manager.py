import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add root to sys.path to allow importing modules
sys.path.append(os.getcwd())

from import_manager import ImportManager

class TestImportManager(unittest.TestCase):
    def setUp(self):
        with patch('import_manager.StoryManager'), patch('import_manager.LibraryManager'):
            self.im = ImportManager()

    @patch('import_manager.os.walk')
    @patch('import_manager.epub.read_epub')
    @patch('import_manager.Path')
    def test_scan_directory(self, mock_path_cls, mock_read_epub, mock_walk):
        # Custom mock for Path to handle different inputs
        def path_side_effect(arg):
            m = MagicMock()
            str_arg = str(arg)
            m.__str__.return_value = str_arg

            if str_arg == '/lib':
                m.resolve.return_value = m
                m.exists.return_value = True
                m.is_dir.return_value = True
                # Mock joining
                def div_side_effect(other):
                    return path_side_effect(f"{str_arg}/{other}")
                m.__truediv__.side_effect = div_side_effect
            else:
                m.name = os.path.basename(str_arg)
                parts = m.name.rsplit('.', 1)
                m.stem = parts[0]
                m.suffix = f".{parts[1]}" if len(parts) > 1 else ""

            return m

        mock_path_cls.side_effect = path_side_effect

        # Setup mock directory structure
        mock_walk.return_value = [
            ('/lib', [], ['book.epub', 'manual.pdf', 'page.html', 'ignore.txt'])
        ]

        # Setup mock epub
        mock_book = MagicMock()
        mock_book.get_metadata.side_effect = lambda ns, key: [['Test Title']] if key == 'title' else [['Test Author']]
        mock_read_epub.return_value = mock_book

        # Mock open for HTML reading
        # We need to mock open specifically for the HTML file path

        # Since we can't easily predict the exact object passed to open (it's the mock path object),
        # we'll mock open globally but only return content for html

        mock_open = unittest.mock.mock_open(read_data="<html><head><title>HTML Story</title></head><body></body></html>")

        with patch('builtins.open', mock_open):
             results = self.im.scan_directory('/lib')

        self.assertEqual(len(results), 3) # epub, pdf, html

        # Check EPUB
        epub_res = next(r for r in results if r['filename'] == 'book.epub')
        self.assertEqual(epub_res['title'], 'Test Title')

        # Check PDF
        pdf_res = next(r for r in results if r['filename'] == 'manual.pdf')
        self.assertEqual(pdf_res['title'], 'manual') # fallback to stem

        # Check HTML
        html_res = next(r for r in results if r['filename'] == 'page.html')
        self.assertEqual(html_res['title'], 'HTML Story') # from BS4

if __name__ == '__main__':
    unittest.main()
