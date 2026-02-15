import unittest
from unittest.mock import MagicMock, patch, mock_open
import worker

class TestWorker(unittest.TestCase):
    @patch('worker.init_db')
    @patch('worker.time.sleep')
    @patch('worker.SessionLocal')
    @patch('worker.RoyalRoadSource')
    @patch('worker.open', new_callable=mock_open)
    @patch('worker.os.makedirs')
    def test_worker_loop_success(self, mock_makedirs, mock_file, MockSource, MockSession, mock_sleep, mock_init_db):
        # Mock session and chapter
        mock_session = MagicMock()
        MockSession.return_value = mock_session

        mock_chapter = MagicMock()
        mock_chapter.id = 1
        mock_chapter.title = "Chapter One"
        mock_chapter.source_url = "http://example.com/ch1"
        mock_chapter.status = "pending"

        mock_story = MagicMock()
        mock_story.id = 101
        mock_story.title = "My Story"
        mock_chapter.story = mock_story

        # Setup query chain
        # session.query(Chapter).filter(...).order_by(...).with_for_update().first()
        mock_session.query.return_value.filter.return_value.order_by.return_value.with_for_update.return_value.first.return_value = mock_chapter

        # Break loop
        mock_sleep.side_effect = InterruptedError("Stop loop")

        # Mock Source
        mock_provider = MockSource.return_value
        mock_provider.get_chapter_content.return_value = "<html>Content</html>"

        try:
            worker.worker()
        except InterruptedError:
            pass

        # Assertions
        mock_session.query.assert_called()
        mock_provider.get_chapter_content.assert_called_with("http://example.com/ch1")
        mock_file.assert_called() # Check file write

        # Check status update
        self.assertEqual(mock_chapter.status, 'downloaded')
        self.assertTrue(mock_chapter.is_downloaded)
        mock_session.commit.assert_called()

    @patch('worker.init_db')
    @patch('worker.time.sleep')
    @patch('worker.SessionLocal')
    @patch('worker.RoyalRoadSource')
    def test_worker_loop_failure(self, MockSource, MockSession, mock_sleep, mock_init_db):
        mock_session = MagicMock()
        MockSession.return_value = mock_session

        mock_chapter = MagicMock()
        mock_chapter.status = "pending"
        mock_chapter.title = "Chapter Fail"
        mock_chapter.story.title = "Story Fail"

        # Setup query
        mock_session.query.return_value.filter.return_value.order_by.return_value.with_for_update.return_value.first.return_value = mock_chapter

        mock_sleep.side_effect = InterruptedError("Stop loop")

        # Mock Source to raise exception
        mock_provider = MockSource.return_value
        mock_provider.get_chapter_content.side_effect = Exception("Download failed")

        try:
            worker.worker()
        except InterruptedError:
            pass

        # Assertions
        self.assertEqual(mock_chapter.status, 'failed')
        mock_session.commit.assert_called()

if __name__ == '__main__':
    unittest.main()
