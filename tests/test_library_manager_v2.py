import unittest
from unittest.mock import MagicMock
import sys
import os
from pathlib import Path

sys.path.append(os.getcwd())
from library_manager import LibraryManager

class TestLibraryManagerUpdates(unittest.TestCase):
    def setUp(self):
        self.lm = LibraryManager()
        self.lm.config = MagicMock()
        self.config_data = {
            'library_path': 'library',
            'story_folder_format': '{Title} ({Id})',
            'chapter_file_format': '{Index} - {Title}',
            'compiled_filename_pattern': '{Title} {StartChapter}-{EndChapter}'
        }
        self.lm.config.get.side_effect = lambda k, d=None: self.config_data.get(k, d)

    def test_new_variables(self):
        story = MagicMock()
        story.title = "My Story"
        story.id = 123
        story.author = "Author"

        c1 = MagicMock()
        c1.index = 1
        c2 = MagicMock()
        c2.index = 10

        # Test Story Path with Id
        path = self.lm.get_story_path(story)
        self.assertEqual(path.name, "My Story (123)")

        # Test Compiled Filename with Start/End
        filename = self.lm.get_compiled_filename(story, "Full", chapters=[c1, c2])
        self.assertEqual(filename, "My Story 1-10.epub")

if __name__ == '__main__':
    unittest.main()
