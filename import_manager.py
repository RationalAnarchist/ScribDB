import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional
import ebooklib
from ebooklib import epub
from story_manager import StoryManager
from library_manager import LibraryManager
from database import SessionLocal, Story

logger = logging.getLogger(__name__)

class ImportManager:
    def __init__(self):
        self.story_manager = StoryManager()
        self.library_manager = LibraryManager()

    def scan_directory(self, path: str) -> List[Dict]:
        """
        Scans a directory for EPUB files and extracts metadata.
        Returns a list of dictionaries with 'title', 'author', 'path', 'filename'.
        """
        search_path = Path(path).resolve()
        if not search_path.exists() or not search_path.is_dir():
            raise ValueError(f"Invalid directory: {path}")

        results = []
        try:
            for root, _, files in os.walk(search_path):
                for file in files:
                    if file.lower().endswith('.epub'):
                        file_path = Path(root) / file
                        metadata = self.extract_metadata(file_path)
                        results.append(metadata)
        except Exception as e:
            logger.error(f"Error scanning directory {path}: {e}")
            raise e

        return results

    def extract_metadata(self, file_path: Path) -> Dict:
        """
        Extracts metadata from an EPUB file.
        Returns a dictionary with 'title', 'author', 'path', 'filename'.
        """
        try:
            # ebooklib can be noisy with warnings, suppress if needed, but for now we just catch exceptions
            book = epub.read_epub(str(file_path))

            # Dublin Core metadata extraction
            title_meta = book.get_metadata('DC', 'title')
            author_meta = book.get_metadata('DC', 'creator')

            # Extract first value if available
            title_str = title_meta[0][0] if title_meta else file_path.stem
            author_str = author_meta[0][0] if author_meta else "Unknown"

            return {
                "title": title_str,
                "author": author_str,
                "path": str(file_path),
                "filename": file_path.name
            }
        except Exception as e:
            logger.error(f"Error reading EPUB {file_path}: {e}")
            # Fallback to filename
            return {
                "title": file_path.stem,
                "author": "Unknown",
                "path": str(file_path),
                "filename": file_path.name,
                "error": str(e)
            }

    def import_story(self, url: str, source_file_path: Optional[str] = None, copy_file: bool = False, delete_source: bool = False) -> int:
        """
        Imports a story from a URL and optionally copies/deletes the source file.
        Returns the story ID.
        """
        logger.info(f"Importing story from URL: {url}")

        # Add story via StoryManager (handles metadata fetch, chapter listing, DB creation)
        story_id = self.story_manager.add_story(url)

        if source_file_path:
            if copy_file:
                self._copy_imported_file(story_id, source_file_path)

            if delete_source:
                try:
                    p = Path(source_file_path)
                    if p.exists():
                        p.unlink()
                        logger.info(f"Deleted source file: {source_file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete source file {source_file_path}: {e}")

        return story_id

    def _copy_imported_file(self, story_id: int, source_file_path: str):
        """
        Helper to copy the imported file to the story's compiled directory.
        """
        try:
            source_path = Path(source_file_path)
            if not source_path.exists():
                logger.warning(f"Source file not found for copy: {source_file_path}")
                return

            session = SessionLocal()
            try:
                story = session.query(Story).filter(Story.id == story_id).first()
                if not story:
                    logger.error(f"Story {story_id} not found for file copy.")
                    return

                # Determine destination filename
                # We use 'Imported' as the suffix/volume indicator for now
                ext = source_path.suffix.lstrip('.')
                if not ext:
                    ext = 'epub'

                # Use LibraryManager to get the correct path
                # Note: get_compiled_absolute_path expects 'suffix' for volume name
                # We'll use "Imported" or the original filename if possible, but LibraryManager enforces structure.
                # Let's use "Imported" to differentiate.
                dest_path = self.library_manager.get_compiled_absolute_path(story, "Imported", ext=ext)

                self.library_manager.ensure_directories(dest_path.parent)

                shutil.copy2(str(source_path), str(dest_path))
                logger.info(f"Copied imported file to {dest_path}")

            except Exception as db_err:
                logger.error(f"Database error during file copy: {db_err}")
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to copy imported file: {e}")
