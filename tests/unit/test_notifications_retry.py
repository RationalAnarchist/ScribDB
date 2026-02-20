import unittest
from unittest.mock import MagicMock, patch
import smtplib
import sys
import os

# Ensure we can import from scrollarr
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from scrollarr.notifications import NotificationManager
from scrollarr.config import config_manager

class TestNotificationRetry(unittest.TestCase):
    def setUp(self):
        # Mock config globally for this test
        self.config_patcher = patch('scrollarr.config.ConfigManager.get')
        self.mock_config = self.config_patcher.start()
        # Ensure we return valid settings
        self.mock_config.side_effect = lambda key, default=None: {
            'smtp_host': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_user': 'user',
            'smtp_password': 'password',
            'smtp_from_email': 'from@example.com'
        }.get(key, default)

        self.notification_manager = NotificationManager()

    def tearDown(self):
        self.config_patcher.stop()

    @patch('time.sleep')
    @patch('smtplib.SMTP')
    def test_send_email_retry_success(self, mock_smtp, mock_sleep):
        # Mock SMTP instance returned by constructor
        smtp_instance = MagicMock()
        mock_smtp.return_value = smtp_instance

        # First call to sendmail raises SMTPException, second succeeds
        smtp_instance.sendmail.side_effect = [smtplib.SMTPException("Transient error"), None]

        self.notification_manager.send_email("to@example.com", "Subject", "Body")

        # Check constructor called
        mock_smtp.assert_called()
        # Check sendmail called twice
        self.assertEqual(smtp_instance.sendmail.call_count, 2)
        # Check if sleep was called once (after first failure)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch('time.sleep')
    @patch('smtplib.SMTP')
    def test_send_email_retry_fail(self, mock_smtp, mock_sleep):
        # Mock SMTP instance
        smtp_instance = MagicMock()
        mock_smtp.return_value = smtp_instance

        # All calls raise Exception
        smtp_instance.sendmail.side_effect = smtplib.SMTPException("Persistent error")

        self.notification_manager.send_email("to@example.com", "Subject", "Body")

        # Should attempt 3 times
        self.assertEqual(smtp_instance.sendmail.call_count, 3)
        # Sleep called 2 times (after 1st and 2nd attempt)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('time.sleep')
    @patch('smtplib.SMTP')
    def test_send_email_connect_retry(self, mock_smtp, mock_sleep):
        # Connection failure (constructor raises exception)
        # First attempt raises ConnectionRefusedError
        # Second attempt returns a mock instance (success)
        smtp_instance = MagicMock()
        mock_smtp.side_effect = [ConnectionRefusedError("Conn Refused"), smtp_instance]

        self.notification_manager.send_email("to@example.com", "Subject", "Body")

        # Check constructor calls
        self.assertEqual(mock_smtp.call_count, 2)
        # Sleep called once
        self.assertEqual(mock_sleep.call_count, 1)
        # Ensure sendmail was called on the instance returned by 2nd call
        smtp_instance.sendmail.assert_called_once()

if __name__ == '__main__':
    unittest.main()
