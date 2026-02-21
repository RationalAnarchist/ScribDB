import os
import logging
import json
import pkgutil
import importlib
import inspect
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func
from .core_logic import SourceManager, BaseSource
from .database import Story, Chapter, Source, SessionLocal, init_db, engine, DownloadHistory
from .config import config_manager
from .notifications import NotificationManager
from .library_manager import LibraryManager
import shutil
import glob
from pathlib import Path
import hashlib
import requests
from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger(__name__)

class StoryManager:
    def __init__(self):
        """
        Initializes the StoryManager.
        Ensures the database is ready and registers providers.
        """
        # Ensure database tables exist
        init_db()

        self.source_manager = SourceManager()
        self.notification_manager = NotificationManager()
        self.library_manager = LibraryManager()
        self.reload_providers()
        logger.info("StoryManager initialized and providers registered.")

    def reload_providers(self):
        """
        Reloads providers from the database and discovers new ones dynamically.
        """
        self.source_manager.clear_providers()
        session = SessionLocal()

        try:
            # Fetch all sources from DB
            all_sources_db = session.query(Source).all()
            sources_map = {s.key: s for s in all_sources_db}

            # Dynamic discovery
            import scrollarr.sources

            package = scrollarr.sources
            # Use pkgutil to iterate modules in the package path

            discovered_providers = []

            for _, name, _ in pkgutil.iter_modules(package.__path__):
                if name == 'templates': # Skip templates directory
                    continue

                full_name = f"scrollarr.sources.{name}"
                try:
                    module = importlib.import_module(full_name)

                    for attribute_name in dir(module):
                        attribute = getattr(module, attribute_name)

                        if inspect.isclass(attribute) and issubclass(attribute, BaseSource):
                            # Skip BaseSource itself
                            if attribute is BaseSource:
                                continue

                            # Skip if imported (not defined in this module)
                            if attribute.__module__ != module.__name__:
                                continue

                            # Instantiate
                            try:
                                provider_instance = attribute()
                                # Check if it has a key
                                if not getattr(provider_instance, 'key', None):
                                    logger.warning(f"Provider {attribute_name} in {name} has no key. Skipping.")
                                    continue

                                discovered_providers.append(provider_instance)
                            except Exception as e:
                                logger.error(f"Failed to instantiate provider {attribute_name}: {e}")

                except Exception as e:
                    logger.error(f"Failed to import module {name}: {e}")

            registered_count = 0
            for provider_instance in discovered_providers:
                key = provider_instance.key

                # Check against DB
                if key in sources_map:
                    source_record = sources_map[key]
                    provider_instance.is_enabled = source_record.is_enabled

                    # Apply config
                    if source_record.config:
                        try:
                            config_data = json.loads(source_record.config)
                            provider_instance.set_config(config_data)
                        except Exception as e:
                            logger.error(f"Failed to load config for {key}: {e}")
                else:
                    # New source found! Add to DB.
                    logger.info(f"New source discovered: {provider_instance.name} ({key})")
                    is_enabled_default = getattr(provider_instance, 'is_enabled_by_default', True)

                    new_source = Source(
                        name=provider_instance.name,
                        key=key,
                        is_enabled=is_enabled_default
                    )
                    session.add(new_source)
                    # Use default enabled state for instance too
                    provider_instance.is_enabled = is_enabled_default

                    try:
                        session.commit()
                        # Add to our local map to avoid duplicates if iterating multiple times (not the case here)
                        sources_map[key] = new_source
                    except Exception as e:
                        logger.error(f"Failed to save new source {key} to DB: {e}")
                        session.rollback()
                        continue

                self.source_manager.register_provider(provider_instance)
                registered_count += 1

            logger.info(f"Reloaded providers. {registered_count} providers registered.")
        except Exception as e:
            logger.error(f"Error reloading providers: {e}")
            session.rollback()
        finally:
            session.close()

    def search(self, query: str, provider_key: Optional[str] = None) -> List[Dict]:
        """
        Searches for stories using enabled providers.
        """
        results = []
        for provider in self.source_manager.providers:
            # Check enabled state
            if not getattr(provider, 'is_enabled', True):
                continue

            # Check if this provider matches the requested key
            p_key = getattr(provider, 'key', None)
            if provider_key and p_key and p_key != provider_key:
                continue

            try:
                # Add provider name to results if not present (handled by provider usually)
                provider_results = provider.search(query)
                results.extend(provider_results)
            except Exception as e:
                logger.error(f"Search failed for provider {p_key}: {e}")

        return results

    def add_story(self, url: str, profile_id: Optional[int] = None, provider_key: Optional[str] = None) -> int:
        """
        Adds a story to the database from the given URL.
        Fetches metadata and chapter list.
        Returns the story ID.
        """
        logger.info(f"Adding story from URL: {url} with provider {provider_key}")

        provider = None
        if provider_key:
            provider = self.source_manager.get_provider_by_key(provider_key)

        if not provider:
            provider = self.source_manager.get_provider_for_url(url)

        if not provider:
            raise ValueError(f"No provider found for URL: {url}")

        metadata = provider.get_metadata(url)
        chapters_data = provider.get_chapter_list(url)

        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.source_url == url).first()

            if not story:
                logger.info("Creating new story record.")
                story = Story(
                    title=metadata.get('title', 'Unknown'),
                    author=metadata.get('author', 'Unknown'),
                    source_url=url,
                    cover_path=metadata.get('cover_url'),
                    status='Monitoring',
                    description=metadata.get('description'),
                    tags=metadata.get('tags'),
                    rating=metadata.get('rating'),
                    language=metadata.get('language'),
                    publication_status=metadata.get('publication_status', 'Unknown'),
                    profile_id=profile_id if profile_id else 1, # Default to Standard (ID 1)
                    provider_name=provider_key
                )
                session.add(story)
                session.flush()
            else:
                logger.info("Updating existing story record.")
                story.title = metadata.get('title', story.title)
                story.author = metadata.get('author', story.author)
                story.cover_path = metadata.get('cover_url', story.cover_path)
                story.description = metadata.get('description', story.description)
                story.tags = metadata.get('tags', story.tags)
                story.rating = metadata.get('rating', story.rating)
                story.language = metadata.get('language', story.language)
                story.publication_status = metadata.get('publication_status', story.publication_status)

            # Handle chapters
            existing_urls = {c.source_url: c for c in story.chapters}
            new_chapters_count = 0

            for i, chapter_data in enumerate(chapters_data):
                c_url = chapter_data['url']
                published_date = chapter_data.get('published_date')
                volume_title = chapter_data.get('volume_title')
                volume_number = chapter_data.get('volume_number', 1)
                idx = chapter_data.get('index', i + 1)

                tags_list = chapter_data.get('tags', [])
                tags_str = ','.join(tags_list) if tags_list else None

                if c_url not in existing_urls:
                    new_chapter = Chapter(
                        title=chapter_data['title'],
                        source_url=c_url,
                        story_id=story.id,
                        index=idx,
                        status='pending',
                        published_date=published_date,
                        volume_title=volume_title,
                        volume_number=volume_number,
                        tags=tags_str
                    )
                    session.add(new_chapter)
                    new_chapters_count += 1
                else:
                    # Update index if needed
                    existing_chap = existing_urls[c_url]
                    if existing_chap.index != idx:
                        existing_chap.index = idx
                    # Update published_date if missing
                    if not existing_chap.published_date and published_date:
                        existing_chap.published_date = published_date
                    # Update volume info
                    if volume_title and existing_chap.volume_title != volume_title:
                         existing_chap.volume_title = volume_title
                    if volume_number and existing_chap.volume_number != volume_number:
                         existing_chap.volume_number = volume_number
                    # Update tags
                    if tags_str and existing_chap.tags != tags_str:
                         existing_chap.tags = tags_str

            story.last_checked = func.now()
            if new_chapters_count > 0:
                story.last_updated = func.now()

            session.commit()
            logger.info(f"Story '{story.title}' processed. Added {new_chapters_count} new chapters.")

            # Save metadata
            self.save_metadata(story)

            return story.id

        except Exception as e:
            session.rollback()
            logger.error(f"Error adding story: {e}")
            raise e
        finally:
            session.close()

    def get_pending_chapters(self):
        """
        Returns all chapters marked as 'pending' across all monitored stories.
        """
        session = SessionLocal()
        try:
            chapters = session.query(Chapter).join(Story).options(joinedload(Chapter.story)).filter(
                Story.is_monitored == True,
                Chapter.status == 'pending'
            ).all()
            session.expunge_all()
            return chapters
        finally:
            session.close()

    def save_metadata(self, story):
        """
        Saves story metadata and chapter status to a JSON file.
        """
        try:
            # Construct story metadata
            story_data = {
                'id': story.id,
                'title': story.title,
                'author': story.author,
                'source_url': story.source_url,
                'provider_name': story.provider_name,
                'status': story.status,
                'description': story.description,
                'tags': story.tags,
                'rating': story.rating,
                'language': story.language,
                'publication_status': story.publication_status,
                'profile_id': story.profile_id,
                'last_updated': story.last_updated.isoformat() if story.last_updated else None,
                'last_checked': story.last_checked.isoformat() if story.last_checked else None,
                'chapters': []
            }

            story_path = self.library_manager.get_story_path(story)

            # Add chapters
            if story.chapters:
                sorted_chapters = sorted(story.chapters, key=lambda c: c.index)
                for chapter in sorted_chapters:
                    local_path_rel = None
                    if chapter.local_path:
                        try:
                            # Try to make path relative to story folder
                            abs_path = Path(chapter.local_path).resolve()
                            story_abs_path = story_path.resolve()
                            if str(abs_path).startswith(str(story_abs_path)):
                                local_path_rel = str(abs_path.relative_to(story_abs_path))
                            else:
                                local_path_rel = chapter.local_path # Keep absolute if outside
                        except Exception:
                            local_path_rel = chapter.local_path

                    story_data['chapters'].append({
                        'index': chapter.index,
                        'title': chapter.title,
                        'url': chapter.source_url,
                        'status': chapter.status,
                        'is_downloaded': chapter.is_downloaded,
                        'local_path': local_path_rel,
                        'volume_number': chapter.volume_number,
                        'volume_title': chapter.volume_title,
                        'published_date': chapter.published_date.isoformat() if chapter.published_date else None,
                        'tags': chapter.tags
                    })

            # Get path
            metadata_path = self.library_manager.get_metadata_absolute_path(story)
            self.library_manager.ensure_directories(metadata_path.parent)

            # Write file
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(story_data, f, indent=4, ensure_ascii=False)

            logger.debug(f"Saved metadata for story {story.id} to {metadata_path}")

        except Exception as e:
            logger.error(f"Failed to save metadata for story {story.id}: {e}")

    def _get_last_chapter_info(self, story):
        """Helper to extract last chapter info for optimization."""
        if not story.chapters:
            return None

        sorted_chapters = sorted(story.chapters, key=lambda c: c.index, reverse=True)
        if sorted_chapters:
            lc = sorted_chapters[0]
            return {
                'url': lc.source_url,
                'title': lc.title,
                'volume_title': lc.volume_title,
                'volume_number': lc.volume_number,
                'index': lc.index
            }
        return None

    def list_stories(self):
        """
        Lists all stories in the database with their download progress.
        Returns a list of dictionaries.
        """
        session = SessionLocal()
        try:
            stories = session.query(Story).all()
            result = []
            for story in stories:
                total = len(story.chapters)
                downloaded = sum(1 for c in story.chapters if c.is_downloaded)
                result.append({
                    'id': story.id,
                    'title': story.title,
                    'author': story.author,
                    'downloaded': downloaded,
                    'total': total
                })
            return result
        finally:
            session.close()

    def compile_story(self, story_id: int):
        """
        Compiles the story into an EPUB file.
        Returns the path of the generated EPUB.
        """
        # Delegate to EbookBuilder
        from .ebook_builder import EbookBuilder
        builder = EbookBuilder()
        return builder.compile_full_story(story_id)

    def update_library(self):
        """
        Iterates through all stories in the database.
        For each story, fetches the current list of chapters from the web.
        Compares the web list to the database list.
        Creates a new Chapter record with status='pending' for any URL that does not exist in the database.
        """
        logger.info("Starting library update...")
        session = SessionLocal()
        try:
            # Iterate through all stories
            stories = session.query(Story).all()

            for story in stories:
                try:
                    logger.info(f"Checking updates for story: {story.title}")

                    provider = None
                    if story.provider_name:
                        provider = self.source_manager.get_provider_by_key(story.provider_name)

                    if not provider:
                        provider = self.source_manager.get_provider_for_url(story.source_url)

                    if not provider:
                        logger.warning(f"No provider found for story: {story.title} ({story.source_url})")
                        continue

                    # Fetch metadata and update story
                    try:
                        metadata = provider.get_metadata(story.source_url)
                        story.title = metadata.get('title', story.title)
                        story.author = metadata.get('author', story.author)
                        story.cover_path = metadata.get('cover_url', story.cover_path)
                        story.description = metadata.get('description', story.description)
                        story.tags = metadata.get('tags', story.tags)
                        story.rating = metadata.get('rating', story.rating)
                        story.language = metadata.get('language', story.language)
                        story.publication_status = metadata.get('publication_status', story.publication_status)
                    except Exception as meta_err:
                        logger.warning(f"Failed to update metadata for {story.title}: {meta_err}")

                    # Determine last chapter for optimization
                    last_chapter = self._get_last_chapter_info(story)

                    # Fetch current chapters from source
                    remote_chapters = provider.get_chapter_list(story.source_url, last_chapter=last_chapter)

                    # Get existing chapters from DB
                    existing_chapter_urls = {c.source_url for c in story.chapters}

                    new_chapters_count = 0
                    for i, chap_data in enumerate(remote_chapters):
                        published_date = chap_data.get('published_date')
                        volume_title = chap_data.get('volume_title')
                        volume_number = chap_data.get('volume_number', 1)
                        idx = chap_data.get('index', i + 1)

                        tags_list = chap_data.get('tags', [])
                        tags_str = ','.join(tags_list) if tags_list else None

                        if chap_data['url'] not in existing_chapter_urls:
                            new_chapter = Chapter(
                                title=chap_data['title'],
                                source_url=chap_data['url'],
                                story_id=story.id,
                                index=idx,
                                status='pending',
                                published_date=published_date,
                                volume_title=volume_title,
                                volume_number=volume_number,
                                tags=tags_str
                            )
                            session.add(new_chapter)
                            new_chapters_count += 1
                        else:
                             # Update date for existing chapters if missing
                             for ec in story.chapters:
                                 if ec.source_url == chap_data['url']:
                                     if not ec.published_date and published_date:
                                         ec.published_date = published_date
                                     # Update index
                                     if ec.index != idx:
                                         ec.index = idx
                                     if volume_title and ec.volume_title != volume_title:
                                         ec.volume_title = volume_title
                                     if volume_number and ec.volume_number != volume_number:
                                         ec.volume_number = volume_number
                                     if tags_str and ec.tags != tags_str:
                                         ec.tags = tags_str
                                     break

                    story.last_checked = func.now()
                    if new_chapters_count > 0:
                        story.last_updated = func.now()
                        logger.info(f"Found {new_chapters_count} new chapters for '{story.title}'")

                        # Notify
                        self.notification_manager.dispatch('on_new_chapters', {
                            'story_title': story.title,
                            'new_chapters_count': new_chapters_count,
                            'story_id': story.id
                        })
                    else:
                        logger.info(f"No new chapters for '{story.title}'")

                    session.commit()

                    # Save metadata
                    self.save_metadata(story)

                except Exception as e:
                    logger.error(f"Error updating story '{story.title}': {e}")
                    session.rollback()

            logger.info("Library update completed.")

        except Exception as e:
            logger.error(f"Critical error during library update: {e}")
        finally:
            session.close()

    def download_missing_chapters(self, story_id: int):
        """
        Downloads content for all chapters of the story that are not yet downloaded.
        """
        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.id == story_id).first()
            if not story:
                raise ValueError(f"Story with ID {story_id} not found.")

            logger.info(f"Checking missing chapters for '{story.title}'...")

            # Get provider again
            provider = self.source_manager.get_provider_for_url(story.source_url)
            if not provider:
                 raise ValueError(f"Provider not found for story URL: {story.source_url}")

            missing_chapters = session.query(Chapter).filter(
                Chapter.story_id == story_id,
                Chapter.is_downloaded == False
            ).all()

            if not missing_chapters:
                logger.info("No missing chapters to download.")
                return

            logger.info(f"Found {len(missing_chapters)} chapters to download.")

            for chapter in missing_chapters:
                logger.info(f"Downloading chapter: {chapter.title}")
                try:
                    content = provider.get_chapter_content(chapter.source_url)

                    # Determine path using LibraryManager
                    filepath = self.library_manager.get_chapter_absolute_path(story, chapter)
                    self.library_manager.ensure_directories(filepath.parent)

                    # Process images
                    try:
                        soup = BeautifulSoup(content, 'html.parser')
                        images = soup.find_all('img')
                        if images:
                            images_dir = self.library_manager.get_images_dir(story)
                            self.library_manager.ensure_directories(images_dir)

                            modified = False
                            for img in images:
                                src = img.get('src')
                                if not src or not src.startswith('http'):
                                    continue

                                # Generate filename
                                ext = 'jpg'
                                if '.' in src.split('/')[-1]:
                                    ext_cand = src.split('/')[-1].split('.')[-1].split('?')[0]
                                    if len(ext_cand) <= 4 and ext_cand.isalnum():
                                        ext = ext_cand

                                filename = f"img_{story.id}_{hashlib.md5(src.encode()).hexdigest()[:10]}.{ext}"
                                local_img_path = images_dir / filename

                                if not local_img_path.exists():
                                    try:
                                        # Simple download
                                        img_resp = requests.get(src, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                                        if img_resp.status_code == 200:
                                            with open(local_img_path, 'wb') as f:
                                                f.write(img_resp.content)
                                            logger.debug(f"Downloaded image {filename}")
                                        else:
                                            logger.warning(f"Failed to download image {src}: Status {img_resp.status_code}")
                                    except Exception as img_err:
                                        logger.warning(f"Error downloading image {src}: {img_err}")

                                if local_img_path.exists():
                                    # Update src to relative path
                                    try:
                                        rel_path = os.path.relpath(local_img_path, filepath.parent)
                                        # Ensure forward slashes for HTML
                                        img['src'] = rel_path.replace(os.sep, '/')
                                        modified = True
                                    except ValueError:
                                        pass

                            if modified:
                                content = str(soup)
                    except Exception as soup_err:
                        logger.error(f"Error processing images for chapter {chapter.title}: {soup_err}")

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                    chapter.local_path = str(filepath)
                    chapter.is_downloaded = True
                    chapter.status = 'downloaded'
                    session.commit() # Commit after each chapter to save progress

                except Exception as e:
                    logger.error(f"Failed to download chapter {chapter.title}: {e}")
                    chapter.status = 'failed'
                    session.commit()
                    # Optionally continue to next chapter or break

            # Save metadata
            self.save_metadata(story)

        finally:
            session.close()

    def _update_metadata(self, story, provider):
        """
        Helper method to update story metadata using the given provider.
        """
        try:
            metadata = provider.get_metadata(story.source_url)
            story.title = metadata.get('title', story.title)
            story.author = metadata.get('author', story.author)
            story.cover_path = metadata.get('cover_url', story.cover_path)
            story.description = metadata.get('description', story.description)
            story.tags = metadata.get('tags', story.tags)
            story.rating = metadata.get('rating', story.rating)
            story.language = metadata.get('language', story.language)
            story.publication_status = metadata.get('publication_status', story.publication_status)
        except Exception as meta_err:
            logger.warning(f"Failed to update metadata for {story.title}: {meta_err}")

    def fill_missing_metadata(self):
        """
        Finds stories with missing metadata (empty description) and attempts to update them.
        """
        logger.info("Checking for stories with missing metadata...")
        session = SessionLocal()
        try:
            # Check for missing description as a proxy for missing metadata
            stories = session.query(Story).filter(
                (Story.description == None) | (Story.description == "")
            ).all()

            if not stories:
                logger.info("No stories found with missing metadata.")
                return

            logger.info(f"Found {len(stories)} stories with missing metadata.")

            for story in stories:
                provider = None
                if story.provider_name:
                    provider = self.source_manager.get_provider_by_key(story.provider_name)
                if not provider:
                    provider = self.source_manager.get_provider_for_url(story.source_url)

                if provider:
                    logger.info(f"Updating metadata for: {story.title}")
                    self._update_metadata(story, provider)

                    # Save metadata
                    self.save_metadata(story)

            session.commit()
        except Exception as e:
            logger.error(f"Error in fill_missing_metadata: {e}")
        finally:
            session.close()

    def check_story_updates(self, story_id: int):
        """
        Fetches metadata and chapter list for a single story and updates the database.
        """
        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.id == story_id).first()
            if not story:
                raise ValueError(f"Story with ID {story_id} not found")

            logger.info(f"Checking updates for story: {story.title}")

            provider = None
            if story.provider_name:
                provider = self.source_manager.get_provider_by_key(story.provider_name)

            if not provider:
                provider = self.source_manager.get_provider_for_url(story.source_url)

            if not provider:
                raise ValueError(f"No provider found for story: {story.title}")

            # Fetch metadata and update story
            self._update_metadata(story, provider)

            # Determine last chapter for optimization
            last_chapter = self._get_last_chapter_info(story)

            # Fetch current chapters from source
            remote_chapters = provider.get_chapter_list(story.source_url, last_chapter=last_chapter)

            # Get existing chapters from DB
            existing_chapter_urls = {c.source_url for c in story.chapters}

            new_chapters_count = 0
            for i, chap_data in enumerate(remote_chapters):
                published_date = chap_data.get('published_date')
                volume_title = chap_data.get('volume_title')
                volume_number = chap_data.get('volume_number', 1)
                idx = chap_data.get('index', i + 1)

                tags_list = chap_data.get('tags', [])
                tags_str = ','.join(tags_list) if tags_list else None

                if chap_data['url'] not in existing_chapter_urls:
                    new_chapter = Chapter(
                        title=chap_data['title'],
                        source_url=chap_data['url'],
                        story_id=story.id,
                        index=idx,
                        status='pending',
                        published_date=published_date,
                        volume_title=volume_title,
                        volume_number=volume_number,
                        tags=tags_str
                    )
                    session.add(new_chapter)
                    new_chapters_count += 1
                else:
                    # Update existing
                     for ec in story.chapters:
                         if ec.source_url == chap_data['url']:
                             if not ec.published_date and published_date:
                                 ec.published_date = published_date
                             if ec.index != idx:
                                 ec.index = idx
                             if volume_title and ec.volume_title != volume_title:
                                 ec.volume_title = volume_title
                             if volume_number and ec.volume_number != volume_number:
                                 ec.volume_number = volume_number
                             if tags_str and ec.tags != tags_str:
                                 ec.tags = tags_str
                             break

            story.last_checked = func.now()
            if new_chapters_count > 0:
                story.last_updated = func.now()
                logger.info(f"Found {new_chapters_count} new chapters for '{story.title}'")

                # Notify
                self.notification_manager.dispatch('on_new_chapters', {
                    'story_title': story.title,
                    'new_chapters_count': new_chapters_count,
                    'story_id': story.id
                })
            else:
                logger.info(f"No new chapters for '{story.title}'")

            session.commit()

            # Save metadata
            self.save_metadata(story)

            return new_chapters_count

        except Exception as e:
            logger.error(f"Error checking updates for story {story_id}: {e}")
            session.rollback()
            raise e
        finally:
            session.close()

    def retry_failed_chapters(self, story_id: int):
        """
        Resets 'failed' chapters to 'pending' for the given story.
        """
        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.id == story_id).first()
            if not story:
                raise ValueError(f"Story with ID {story_id} not found")

            failed_chapters = session.query(Chapter).filter(
                Chapter.story_id == story_id,
                Chapter.status == 'failed'
            ).all()

            count = 0
            for chapter in failed_chapters:
                chapter.status = 'pending'
                count += 1

            session.commit()
            logger.info(f"Queued {count} failed chapters for retry for story '{story.title}'")
            return count
        except Exception as e:
            logger.error(f"Error retrying chapters for story {story_id}: {e}")
            session.rollback()
            raise e
        finally:
            session.close()
    def get_story_schedule(self, story_id: int):
        """
        Analyzes the release schedule for a story and predicts next chapter.
        """
        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.id == story_id).first()
            if not story:
                return None

            chapters = session.query(Chapter).filter(
                Chapter.story_id == story_id,
                Chapter.published_date != None
            ).order_by(Chapter.published_date).all()

            if len(chapters) < 2:
                return {
                    'story_title': story.title,
                    'prediction': None,
                    'history': []
                }

            # Calculate intervals
            dates = [c.published_date for c in chapters]
            intervals = []
            for i in range(1, len(dates)):
                delta = dates[i] - dates[i-1]
                intervals.append(delta.total_seconds())

            avg_interval_seconds = sum(intervals) / len(intervals)

            last_date = dates[-1]
            next_date = last_date + timedelta(seconds=avg_interval_seconds)

            return {
                'story_title': story.title,
                'prediction': next_date,
                'avg_interval_days': avg_interval_seconds / 86400,
                'history_count': len(chapters)
            }
        finally:
            session.close()

    def delete_story(self, story_id: int, delete_content: bool):
        """
        Deletes a story and optionally its downloaded content.
        """
        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.id == story_id).first()
            if not story:
                raise ValueError(f"Story with ID {story_id} not found")

            if delete_content:
                logger.info(f"Deleting content for story '{story.title}'...")

                # Delete new structure
                story_path = self.library_manager.get_story_path(story)
                if story_path.exists():
                    try:
                        shutil.rmtree(story_path)
                        logger.info(f"Deleted story directory: {story_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete directory {story_path}: {e}")

                # Cleanup Legacy Paths (Best Effort)
                download_path = config_manager.get('download_path', 'verification_downloads')
                try:
                    candidates = glob.glob(os.path.join(download_path, f"{story_id}_*"))
                    for cand in candidates:
                        if os.path.isdir(cand):
                            shutil.rmtree(cand)
                            logger.info(f"Deleted legacy directory: {cand}")
                except Exception as e:
                     logger.error(f"Error during fallback deletion: {e}")

            # Delete database records
            # Manually delete history
            session.query(DownloadHistory).filter(DownloadHistory.story_id == story_id).delete()

            # Delete story (cascades to chapters)
            session.delete(story)
            session.commit()
            logger.info(f"Story {story_id} deleted.")

        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting story {story_id}: {e}")
            raise e
        finally:
            session.close()

    def get_calendar_events(self, start=None, end=None):
        """
        Returns calendar events for all stories.
        """
        session = SessionLocal()
        try:
            stories = session.query(Story).filter(Story.is_monitored == True).all()
            events = []

            for story in stories:
                # Get history
                chapters = session.query(Chapter).filter(
                    Chapter.story_id == story.id,
                    Chapter.published_date != None
                ).all()

                for chap in chapters:
                    events.append({
                        'title': f"{story.title} - {chap.title}",
                        'start': chap.published_date.isoformat(),
                        'color': '#3788d8', # Blue for past
                        'url': f"/story/{story.id}"
                    })

                # Prediction (we call internal method but need new session or pass session)
                # To avoid session conflict, we can reimplement logic or use the same session if refactored.
                # Here we just re-query chapters which is fine but slightly inefficient.
                # Actually, calling self.get_story_schedule creates a NEW session. This is fine as long as we are not in a transaction that blocks.
                # But since we are inside a session here, it might be better to close this one or make get_story_schedule accept a session.

                # Let's reimplement lightweight prediction here or rely on the other method.
                # Since we are using SQLite with check_same_thread=False, it should be OK.

                # But wait, get_story_schedule opens a session.
                # Let's just use the current session to query chapters for prediction.

                sorted_dates = sorted([c.published_date for c in chapters if c.published_date])
                if len(sorted_dates) >= 2:
                     intervals = []
                     for i in range(1, len(sorted_dates)):
                         delta = sorted_dates[i] - sorted_dates[i-1]
                         intervals.append(delta.total_seconds())

                     avg = sum(intervals) / len(intervals)

                     # Predict next 5 chapters
                     last_date = sorted_dates[-1]
                     now = datetime.now()

                     # Start from the last known date
                     next_prediction = last_date + timedelta(seconds=avg)

                     # Find the next valid slot in the FUTURE
                     # We keep adding the interval to the original cadence until we land in the future.
                     # This preserves the rhythm (e.g. every 2 days) rather than resetting the clock to 'now'.
                     while next_prediction < now:
                         next_prediction += timedelta(seconds=avg)

                     for i in range(5):
                        events.append({
                            'title': f"{story.title} - Predicted",
                            'start': next_prediction.isoformat(),
                            'color': '#28a745', # Green
                            'url': f"/story/{story.id}",
                            'allDay': True
                        })
                        next_prediction += timedelta(seconds=avg)

            return events
        finally:
            session.close()
