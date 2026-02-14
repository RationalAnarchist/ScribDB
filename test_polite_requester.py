import unittest
from unittest.mock import patch, Mock
import time
from polite_requester import PoliteRequester

class TestPoliteRequester(unittest.TestCase):
    def setUp(self):
        self.requester = PoliteRequester(delay_range=(2, 5))

    @patch('time.sleep')
    @patch('requests.get')
    def test_get_request_calls_requests_with_correct_headers(self, mock_get, mock_sleep):
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        url = "http://example.com"
        self.requester.get(url)

        # Verify requests.get was called with the URL and headers
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], url)
        self.assertIn('User-Agent', kwargs['headers'])
        self.assertIn('Accept', kwargs['headers'])
        self.assertIn('Accept-Language', kwargs['headers'])

    @patch('time.sleep')
    @patch('requests.get')
    def test_get_request_waits_random_delay(self, mock_get, mock_sleep):
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        url = "http://example.com"
        self.requester.get(url)

        # Verify time.sleep was called
        mock_sleep.assert_called_once()
        # Verify the delay was within range
        delay = mock_sleep.call_args[0][0]
        self.assertGreaterEqual(delay, 2)
        self.assertLessEqual(delay, 5)

    @patch('time.sleep')
    @patch('requests.get')
    def test_get_request_raises_for_status(self, mock_get, mock_sleep):
        # Setup mock response to raise an error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP Error")
        mock_get.return_value = mock_response

        url = "http://example.com"
        with self.assertRaises(Exception):
            self.requester.get(url)

if __name__ == '__main__':
    unittest.main()
