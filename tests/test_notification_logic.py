import os
import unittest
from unittest.mock import MagicMock, patch
from database import Story, Base, NotificationSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database
from notifications import NotificationManager

class TestNotificationLogic(unittest.TestCase):
    def setUp(self):
        # Setup temporary DB
        self.test_db_url = 'sqlite:///test_notifications.db'
        self.test_engine = create_engine(self.test_db_url, connect_args={"check_same_thread": False})
        self.TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.test_engine)

        # Patch database
        self.original_engine = database.engine
        self.original_sessionlocal = database.SessionLocal
        database.engine = self.test_engine
        database.SessionLocal = self.TestSessionLocal

        # Create tables
        Base.metadata.create_all(bind=self.test_engine)

        # Patch SessionLocal in notifications module
        self.patcher = patch('notifications.SessionLocal', self.TestSessionLocal)
        self.patcher.start()

        self.nm = NotificationManager()

    def tearDown(self):
        self.patcher.stop()
        Base.metadata.drop_all(bind=self.test_engine)
        database.engine = self.original_engine
        database.SessionLocal = self.original_sessionlocal
        self.test_engine.dispose()
        if os.path.exists("test_notifications.db"):
            try:
                os.remove("test_notifications.db")
            except:
                pass

    @patch('notifications.NotificationManager.send_email')
    @patch('notifications.NotificationManager._get_enabled_notifications')
    def test_dispatch_respects_story_setting(self, mock_get_settings, mock_send_email):
        # 1. Create a story with notifications ENABLED (default)
        session = self.TestSessionLocal()
        story = Story(title="Enabled Story", author="Me", source_url="http://enabled", notify_on_new_chapter=True)
        session.add(story)
        session.commit()
        story_id = story.id
        session.close()

        # Mock settings to return a setting
        mock_setting = MagicMock(spec=NotificationSettings)
        mock_setting.kind = 'email'
        mock_setting.target = 'test@example.com'
        mock_setting.events = 'on_new_chapters'
        mock_setting.attach_file = False
        mock_get_settings.return_value = [mock_setting]

        # 2. Dispatch event
        self.nm.dispatch('on_new_chapters', {'story_id': story_id, 'story_title': 'Enabled Story', 'new_chapters_count': 1})

        # 3. Verify email sent
        mock_send_email.assert_called()
        mock_send_email.reset_mock()

        # 4. Update story to DISABLE notifications
        session = self.TestSessionLocal()
        story = session.query(Story).filter(Story.id == story_id).first()
        story.notify_on_new_chapter = False
        session.commit()
        session.close()

        # 5. Dispatch event
        self.nm.dispatch('on_new_chapters', {'story_id': story_id, 'story_title': 'Enabled Story', 'new_chapters_count': 1})

        # 6. Verify email NOT sent
        mock_send_email.assert_not_called()

    @patch('notifications.NotificationManager.send_email')
    @patch('notifications.NotificationManager._get_enabled_notifications')
    def test_dispatch_allows_other_events(self, mock_get_settings, mock_send_email):
        # 1. Create a story with notifications DISABLED
        session = self.TestSessionLocal()
        story = Story(title="Disabled Story", author="Me", source_url="http://disabled", notify_on_new_chapter=False)
        session.add(story)
        session.commit()
        story_id = story.id
        session.close()

        mock_setting = MagicMock(spec=NotificationSettings)
        mock_setting.kind = 'email'
        mock_setting.target = 'test@example.com'
        mock_setting.events = 'on_failure'
        mock_setting.attach_file = False
        mock_get_settings.return_value = [mock_setting]

        # 2. Dispatch 'on_failure' event
        self.nm.dispatch('on_failure', {'story_id': story_id, 'story_title': 'Disabled Story', 'error': 'oops'})

        # 3. Verify email SENT (because we only block success/new chapters if explicitly implemented, but wait...
        # My implementation blocked 'on_download' AND 'on_new_chapters'.
        # It did NOT block 'on_failure'.
        mock_send_email.assert_called()

if __name__ == '__main__':
    unittest.main()
