import os
import unittest
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from scrollarr.database import Base, Story
from scrollarr.app import app, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_api.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

class TestApiNotifications(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        if os.path.exists("./test_api.db"):
            os.remove("./test_api.db")

    def test_toggle_notifications(self):
        # Create a story
        story = Story(title="Test Story", author="Test Author", source_url="http://test.com", notify_on_new_chapter=True)
        self.db.add(story)
        self.db.commit()
        story_id = story.id

        # Initial state
        self.assertTrue(story.notify_on_new_chapter)

        # Call API to toggle off
        response = self.client.post(f"/api/story/{story_id}/toggle-notifications")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['notify_on_new_chapter'])

        # Verify DB state
        self.db.refresh(story)
        self.assertFalse(story.notify_on_new_chapter)

        # Call API to toggle on
        response = self.client.post(f"/api/story/{story_id}/toggle-notifications")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['notify_on_new_chapter'])

        # Verify DB state
        self.db.refresh(story)
        self.assertTrue(story.notify_on_new_chapter)

if __name__ == '__main__':
    unittest.main()
