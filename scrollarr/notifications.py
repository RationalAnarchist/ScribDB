import logging
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import requests
import json
import os
from .database import SessionLocal, NotificationSettings, Story
from .config import config_manager
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self):
        pass

    def _get_enabled_notifications(self, event_type: str) -> List[NotificationSettings]:
        session = SessionLocal()
        try:
            # Query all enabled settings
            settings = session.query(NotificationSettings).filter(
                NotificationSettings.enabled == True
            ).all()

            # Filter by event in python because we store events as comma-separated string
            matched = []
            for setting in settings:
                if not setting.events:
                    continue
                events = [e.strip() for e in setting.events.split(',')]
                if event_type in events:
                    matched.append(setting)
            return matched
        except Exception as e:
            logger.error(f"Error fetching notification settings: {e}")
            return []
        finally:
            session.close()

    def send_email(self, target: str, subject: str, body: str, attachment_path: str = None):
        smtp_host = config_manager.get('smtp_host')
        if not smtp_host:
            logger.warning("SMTP host not configured. Cannot send email.")
            return

        smtp_port = int(config_manager.get('smtp_port', 587))
        smtp_user = config_manager.get('smtp_user')
        smtp_pass = config_manager.get('smtp_password')
        from_email = config_manager.get('smtp_from_email', smtp_user)

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = target
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        if attachment_path and os.path.exists(attachment_path):
            try:
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(
                        f.read(),
                        Name=os.path.basename(attachment_path)
                    )
                # After the file is closed
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(part)
            except Exception as e:
                logger.error(f"Failed to attach file {attachment_path}: {e}")

        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, target, msg.as_string())
                server.quit()
                logger.info(f"Email sent to {target}")
                return
            except smtplib.SMTPException as e:
                logger.warning(f"Email attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"Failed to send email to {target} after {max_retries} attempts: {e}")
            except Exception as e:
                # Retry on connection errors too
                logger.warning(f"Email attempt {attempt+1}/{max_retries} failed with error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"Failed to send email to {target} after {max_retries} attempts: {e}")

    def send_webhook(self, target: str, message: str, context: Dict[str, Any]):
        # Sanitize context for JSON serialization
        safe_context = {}
        for k, v in context.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                safe_context[k] = v
            else:
                safe_context[k] = str(v)

        # simple payload for Discord/Slack
        payload = {
            "content": message, # Discord
            "text": message,    # Slack
            "data": safe_context # Generic
        }

        try:
            response = requests.post(target, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Webhook sent to {target}")
        except Exception as e:
            logger.error(f"Failed to send webhook to {target}: {e}")

    def dispatch(self, event: str, context: Dict[str, Any]):
        # Check if story specific notifications are disabled
        story_id = context.get('story_id')
        if story_id and event in ['on_new_chapters', 'on_download']:
            session = SessionLocal()
            try:
                story = session.query(Story).filter(Story.id == story_id).first()
                if story and not story.notify_on_new_chapter:
                    logger.info(f"Skipping notification for story {story_id} (notifications disabled).")
                    return
            except Exception as e:
                logger.error(f"Error checking story notification settings: {e}")
            finally:
                session.close()

        settings = self._get_enabled_notifications(event)
        if not settings:
            return

        logger.info(f"Dispatching event {event} to {len(settings)} targets.")

        # Prepare message
        story_title = context.get('story_title', 'Unknown Story')
        chapter_title = context.get('chapter_title', '')

        if event == 'on_download':
            subject = f"Downloaded: {story_title} - {chapter_title}"
            message = f"Successfully downloaded: {story_title}\nChapter: {chapter_title}"
        elif event == 'on_failure':
            error = context.get('error', 'Unknown Error')
            subject = f"Failed: {story_title} - {chapter_title}"
            message = f"Download failed for: {story_title}\nChapter: {chapter_title}\nError: {error}"
        elif event == 'on_new_chapters':
            count = context.get('new_chapters_count', 0)
            subject = f"New Chapters: {story_title}"
            message = f"Found {count} new chapters for {story_title}."
        else:
            subject = f"Notification: {event}"
            message = f"Event {event} occurred for {story_title}."

        for setting in settings:
            if setting.kind == 'email':
                attachment = None
                if setting.attach_file and 'file_path' in context:
                    attachment = context.get('file_path')

                self.send_email(setting.target, subject, message, attachment)
            elif setting.kind == 'webhook':
                self.send_webhook(setting.target, message, context)
