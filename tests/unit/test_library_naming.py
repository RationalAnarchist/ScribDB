import unittest
from pathlib import Path
from types import SimpleNamespace
from scrollarr.library_manager import LibraryManager
from scrollarr.config import config_manager

class TestLibraryNaming(unittest.TestCase):
    def setUp(self):
        self.lm = LibraryManager()
        # Mock config
        self.original_config = config_manager.config.copy()

        # Set test formats
        config_manager.set('single_chapter_name_format', '{Title} - Ch{chapNum} - {chapName}')
        config_manager.set('chapter_group_name_format', '{Title} - Ch{startChapNum}-{endChapNum}')
        config_manager.set('volume_name_format', '{Title} - Vol {volNum} - {volName}')
        config_manager.set('full_story_name_format', '{Title} - Full - To Ch{endChapNum}')
        config_manager.set('compiled_filename_pattern', 'Legacy_{Title}_{Volume}')

    def tearDown(self):
        config_manager.config = self.original_config

    def test_single_chapter(self):
        story = SimpleNamespace(title="MyStory", author="Me", id=1)
        chapters = [SimpleNamespace(index=10, title="The Beginning", volume_number=1, volume_title="Vol1")]

        name = self.lm.get_compiled_filename(story, suffix="unused", chapters=chapters, file_type='single')
        self.assertEqual(name, "MyStory - Ch10 - The Beginning.epub")

    def test_chapter_group(self):
        story = SimpleNamespace(title="MyStory", author="Me", id=1)
        chapters = [
            SimpleNamespace(index=10, title="A", volume_number=1, volume_title="Vol1"),
            SimpleNamespace(index=15, title="B", volume_number=1, volume_title="Vol1")
        ]

        name = self.lm.get_compiled_filename(story, suffix="unused", chapters=chapters, file_type='group')
        self.assertEqual(name, "MyStory - Ch10-15.epub")

    def test_volume(self):
        story = SimpleNamespace(title="MyStory", author="Me", id=1)
        chapters = [SimpleNamespace(index=1, title="A", volume_number=3, volume_title="Arc 3")]

        name = self.lm.get_compiled_filename(story, suffix="Vol 3", chapters=chapters, file_type='volume')
        self.assertEqual(name, "MyStory - Vol 3 - Arc 3.epub")

    def test_full_story(self):
        story = SimpleNamespace(title="MyStory", author="Me", id=1)
        chapters = [
            SimpleNamespace(index=1, title="A", volume_number=1, volume_title="Vol1"),
            SimpleNamespace(index=100, title="Z", volume_number=5, volume_title="Vol5")
        ]

        name = self.lm.get_compiled_filename(story, suffix="Full", chapters=chapters, file_type='full')
        self.assertEqual(name, "MyStory - Full - To Ch100.epub")

    def test_legacy_fallback(self):
        story = SimpleNamespace(title="MyStory", author="Me", id=1)
        chapters = [SimpleNamespace(index=1, title="A", volume_number=1, volume_title="Vol1")]

        # file_type defaults to 'legacy' if not passed (or explicit legacy)
        name = self.lm.get_compiled_filename(story, suffix="CustomSuffix", chapters=chapters, file_type='legacy')
        self.assertEqual(name, "Legacy_MyStory_CustomSuffix.epub")

if __name__ == '__main__':
    unittest.main()
