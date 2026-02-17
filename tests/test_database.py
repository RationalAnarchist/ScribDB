import unittest
import sys
import os
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import Base, Story, Chapter, sync_story

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Use in-memory SQLite for testing
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    @patch('database.SourceManager')
    def test_sync_story_new(self, MockSourceManager):
        # Setup mock
        mock_manager = MockSourceManager.return_value
        mock_provider = MagicMock()
        mock_manager.get_provider_for_url.return_value = mock_provider

        url = "http://example.com/story"
        mock_provider.get_metadata.return_value = {
            'title': 'Test Story',
            'author': 'Test Author',
            'cover_url': 'http://example.com/cover.jpg'
        }
        mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/ch1'},
            {'title': 'Chapter 2', 'url': 'http://example.com/ch2'}
        ]

        # Call function
        sync_story(url, session=self.session)

        # Verify Story created
        story = self.session.query(Story).filter_by(source_url=url).first()
        self.assertIsNotNone(story)
        self.assertEqual(story.title, 'Test Story')
        self.assertEqual(story.author, 'Test Author')
        self.assertEqual(story.status, 'Monitoring')
        self.assertTrue(story.is_monitored)

        # Verify Chapters created
        chapters = self.session.query(Chapter).filter_by(story_id=story.id).order_by(Chapter.index).all()
        self.assertEqual(len(chapters), 2)
        titles = [c.title for c in chapters]
        self.assertEqual(titles, ['Chapter 1', 'Chapter 2'])
        self.assertEqual(chapters[0].index, 1)
        self.assertEqual(chapters[1].index, 2)
        self.assertEqual(chapters[0].volume_number, 1)
        self.assertEqual(chapters[0].status, 'pending')

    @patch('database.SourceManager')
    def test_sync_story_update(self, MockSourceManager):
        # Setup existing story
        story = Story(title="Old Title", author="Old Author", source_url="http://example.com/story")
        self.session.add(story)
        self.session.commit()

        # Setup mock
        mock_manager = MockSourceManager.return_value
        mock_provider = MagicMock()
        mock_manager.get_provider_for_url.return_value = mock_provider

        url = "http://example.com/story"
        mock_provider.get_metadata.return_value = {
            'title': 'New Title',
            'author': 'New Author',
            'cover_url': 'http://example.com/cover.jpg'
        }
        mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/ch1'}
        ]

        # Call function
        sync_story(url, session=self.session)

        # Verify Story updated
        self.session.refresh(story)
        self.assertEqual(story.title, 'New Title')
        self.assertEqual(story.author, 'New Author')
        self.assertIsNotNone(story.last_updated)

        # Verify Chapter added
        chapters = self.session.query(Chapter).filter_by(story_id=story.id).all()
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0].title, 'Chapter 1')

    @patch('database.SourceManager')
    def test_sync_story_no_duplicates(self, MockSourceManager):
        # Setup existing story and chapter
        story = Story(title="Title", author="Author", source_url="http://example.com/story")
        # Need to add story first to get ID for chapter, or rely on relationship
        self.session.add(story)
        self.session.flush() # flush to get ID

        chapter = Chapter(title="Chapter 1", source_url="http://example.com/ch1", story_id=story.id)
        self.session.add(chapter)
        self.session.commit()

        # Setup mock
        mock_manager = MockSourceManager.return_value
        mock_provider = MagicMock()
        mock_manager.get_provider_for_url.return_value = mock_provider

        url = "http://example.com/story"
        mock_provider.get_metadata.return_value = {
            'title': 'Title',
            'author': 'Author',
            'cover_url': 'http://example.com/cover.jpg'
        }
        mock_provider.get_chapter_list.return_value = [
            {'title': 'Chapter 1', 'url': 'http://example.com/ch1'},
            {'title': 'Chapter 2', 'url': 'http://example.com/ch2'}
        ]

        # Call function
        sync_story(url, session=self.session)

        # Verify only one new chapter added
        chapters = self.session.query(Chapter).filter_by(story_id=story.id).all()
        self.assertEqual(len(chapters), 2)
        urls = sorted([c.source_url for c in chapters])
        self.assertEqual(urls, ['http://example.com/ch1', 'http://example.com/ch2'])

if __name__ == '__main__':
    unittest.main()
