import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Story, Chapter

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

    def test_story_model(self):
        story = Story(title="Test Story", author="Test Author", source_url="http://example.com")
        self.session.add(story)
        self.session.commit()

        retrieved = self.session.query(Story).first()
        self.assertEqual(retrieved.title, "Test Story")
        self.assertEqual(retrieved.author, "Test Author")

    def test_chapter_model(self):
        story = Story(title="Test Story", author="Test Author", source_url="http://example.com")
        self.session.add(story)
        self.session.flush()

        chapter = Chapter(title="Chapter 1", source_url="http://example.com/1", story_id=story.id)
        self.session.add(chapter)
        self.session.commit()

        retrieved = self.session.query(Chapter).first()
        self.assertEqual(retrieved.title, "Chapter 1")
        self.assertEqual(retrieved.story_id, story.id)

if __name__ == '__main__':
    unittest.main()
