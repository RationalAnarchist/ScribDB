import os
import shutil
import logging
import glob
from pathlib import Path
from .config import config_manager
from .database import Chapter

logger = logging.getLogger(__name__)

class LibraryManager:
    def __init__(self):
        self.config = config_manager

    def get_library_root(self) -> Path:
        """Returns the absolute path to the library root."""
        root = self.config.get('library_path', 'library')
        return Path(root).resolve()

    def sanitize_filename(self, name: str) -> str:
        """Sanitizes a string to be safe for filenames."""
        if not name:
            return "unknown"
        # Keep alphanumeric, space, dot, hyphen, underscore
        safe = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_', '.')]).strip()
        return safe

    def format_string(self, template: str, context: dict) -> str:
        """Formats a string using the given context, with sanitization."""
        safe_context = {k: self.sanitize_filename(str(v)) for k, v in context.items()}
        try:
            return template.format(**safe_context)
        except KeyError as e:
            logger.warning(f"Missing key in format string '{template}': {e}")
            return template # Fallback

    def get_story_path(self, story) -> Path:
        """Returns the path to the story directory."""
        template = self.config.get('story_folder_format', '{Title} ({Id})')
        folder_name = self.format_string(template, {'Title': story.title, 'Author': story.author, 'Id': story.id})
        return self.get_library_root() / folder_name

    def get_chapter_dir(self, story, volume_number=None, volume_title=None) -> Path:
        """Returns the directory where chapters should be stored."""
        story_path = self.get_story_path(story)
        base_chapter_path = story_path / "chapters"

        if volume_number is not None:
            template = self.config.get('volume_folder_format', 'Volume {Volume}')
            vol_name = self.format_string(template, {'Volume': volume_number, 'Title': volume_title or ''})
            return base_chapter_path / vol_name

        return base_chapter_path

    def get_chapter_filename(self, story, chapter) -> str:
        """Returns the filename for a chapter HTML file."""
        template = self.config.get('chapter_file_format', '{Index} - {Title}')
        filename = self.format_string(template, {
            'Index': chapter.index,
            'Title': chapter.title,
            'Volume': chapter.volume_number or 1,
            'StoryTitle': story.title,
            'Id': story.id
        })
        return f"{filename}.html"

    def get_chapter_absolute_path(self, story, chapter) -> Path:
        """Returns the full absolute path for a chapter file."""
        directory = self.get_chapter_dir(story, chapter.volume_number, chapter.volume_title)
        filename = self.get_chapter_filename(story, chapter)
        return directory / filename

    def get_compiled_dir(self, story) -> Path:
        """Returns the directory where compiled ebooks are stored."""
        return self.get_story_path(story) / "compiled"

    def get_compiled_filename(self, story, suffix: str, ext: str = 'epub', chapters: list = None, file_type: str = 'legacy') -> str:
        """Returns the filename for a compiled ebook."""

        # Select template based on file_type
        if file_type == 'single':
            template = self.config.get('single_chapter_name_format', '{Title} - {Index} - {Chapter}')
        elif file_type == 'group':
            template = self.config.get('chapter_group_name_format', '{Title} - {StartChapter} to {EndChapter}')
        elif file_type == 'full':
            template = self.config.get('full_story_name_format', '{Title} - Full story to {EndChapter}')
        elif file_type == 'volume':
            template = self.config.get('volume_name_format', '{Title} - {Volume} - {VolName}')
        else:
            # Fallback to legacy or volume default
            template = self.config.get('compiled_filename_pattern', '{Title} - {Volume}')

        # Initialize placeholders
        start_chap = '?'
        end_chap = '?'
        chap_num = '?'
        chap_name = '?'
        vol_num = '?'
        vol_name = ''

        if chapters and len(chapters) > 0:
            first = chapters[0]
            last = chapters[-1]

            # Handle object vs dict
            if hasattr(first, 'index'):
                 start_chap = first.index
                 end_chap = last.index
                 chap_num = first.index
                 chap_name = first.title
                 vol_num = first.volume_number or '1'
                 vol_name = first.volume_title or ''
            elif isinstance(first, dict):
                 start_chap = first.get('index', '?')
                 end_chap = last.get('index', '?')
                 chap_num = first.get('index', '?')
                 chap_name = first.get('title', '?')
                 vol_num = first.get('volume_number', '1')
                 vol_name = first.get('volume_title', '')

        # Construct context with aliases
        context = {
            'Title': story.title,
            'Author': story.author,
            'Volume': suffix, # Legacy / Fallback
            'StoryTitle': story.title,
            'Id': story.id,
            'StartChapter': start_chap,
            'EndChapter': end_chap,
            # New placeholders
            'chapNum': chap_num,
            'chapName': chap_name,
            'startChapNum': start_chap,
            'endChapNum': end_chap,
            'volNum': vol_num,
            'volName': vol_name,
            # Aliases for template consistency
            'Index': chap_num,
            'Chapter': chap_name,
            'VolName': vol_name,
            'VolNum': vol_num
        }

        filename = self.format_string(template, context)
        if not filename.lower().endswith(f".{ext}"):
            filename += f".{ext}"
        return filename

    def get_compiled_absolute_path(self, story, suffix: str, ext: str = 'epub', chapters: list = None, file_type: str = 'legacy') -> Path:
        """Returns the full absolute path for a compiled ebook."""
        directory = self.get_compiled_dir(story)
        filename = self.get_compiled_filename(story, suffix, ext, chapters, file_type)
        return directory / filename

    def get_metadata_dir(self, story) -> Path:
        """Returns the directory where metadata should be stored."""
        return self.get_story_path(story) / "metadata"

    def get_metadata_absolute_path(self, story) -> Path:
        """Returns the full absolute path for the metadata file."""
        return self.get_metadata_dir(story) / "metadata.json"

    def ensure_directories(self, path: Path):
        """Ensures the directory exists."""
        os.makedirs(path, exist_ok=True)

    def migrate_story(self, session, story) -> bool:
        """
        Migrates a story from legacy structure to new structure.
        Returns True if successful.
        """
        try:
            logger.info(f"Migrating story: {story.title} (ID: {story.id})")

            # 1. Identify old chapter directory
            # Old format: download_path/{id}_{safe_title}
            old_download_path = Path(self.config.get('download_path', 'verification_downloads')).resolve()

            # Reconstruct old safe title logic
            safe_title = "".join([c for c in story.title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(' ', '_')
            old_dir_name = f"{story.id}_{safe_title}"
            old_dir_path = old_download_path / old_dir_name

            # Fallback for old dir search
            if not old_dir_path.exists():
                candidates = list(old_download_path.glob(f"{story.id}_*"))
                if candidates:
                    old_dir_path = candidates[0]

            # 2. Identify old compiled files directory
            # This is hardcoded to 'library' in the old code default config unless changed.
            # Assuming files are in current directory's 'library' folder if not otherwise specified?
            # Or config.get('library_path')?
            # But library_path is now pointing to the NEW root.
            # So we assume old compiled files are in a folder named 'library' at the project root OR wherever config said before.
            # This is ambiguous. Let's assume standard 'library'.
            old_library_path = Path("library").resolve()

            # 3. Create new directories
            new_story_path = self.get_story_path(story)
            compiled_dir = self.get_compiled_dir(story)
            self.ensure_directories(compiled_dir)

            # 4. Move Chapters
            if old_dir_path.exists():
                logger.info(f"Found legacy chapter directory: {old_dir_path}")

                chapters = session.query(Chapter).filter_by(story_id=story.id).all()
                for chapter in chapters:
                    new_chap_path = self.get_chapter_absolute_path(story, chapter)

                    # Ensure parent dir (Volume folder) exists
                    self.ensure_directories(new_chap_path.parent)

                    src = None
                    if chapter.local_path and os.path.exists(chapter.local_path):
                        src = Path(chapter.local_path)
                    else:
                        # Try to guess
                        safe_chap_title = "".join([c for c in chapter.title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(' ', '_')
                        guess_filename = f"{chapter.id}_{safe_chap_title}.html"
                        src = old_dir_path / guess_filename

                    if src and src.exists():
                        try:
                            # Check if already in place
                            if src.resolve() != new_chap_path.resolve():
                                shutil.move(str(src), str(new_chap_path))
                                chapter.local_path = str(new_chap_path)
                                chapter.status = 'downloaded'
                                logger.debug(f"Moved chapter {chapter.id} to {new_chap_path}")
                        except Exception as e:
                            logger.error(f"Failed to move chapter {chapter.id}: {e}")
                    else:
                        logger.warning(f"Source file not found for chapter {chapter.id}")

                session.commit()

                # Remove old directory if empty
                try:
                    if not any(old_dir_path.iterdir()):
                        os.rmdir(old_dir_path)
                        logger.info("Removed empty legacy directory.")
                except Exception as e:
                    logger.warning(f"Could not remove old dir {old_dir_path}: {e}")

            # 5. Move Compiled Files
            # We search for files starting with Title in old_library_path
            if old_library_path.exists():
                safe_title_start = self.sanitize_filename(story.title)
                # Find files that contain the title
                # This is heuristic.
                for file_path in old_library_path.glob(f"*{safe_title_start}*"):
                    if file_path.is_file() and file_path.suffix in ['.epub', '.pdf']:
                        dest = compiled_dir / file_path.name
                        try:
                            if file_path.resolve() != dest.resolve():
                                shutil.move(str(file_path), str(dest))
                                logger.info(f"Moved compiled file {file_path.name} to {dest}")
                        except Exception as e:
                             logger.error(f"Failed to move compiled file {file_path.name}: {e}")

            return True

        except Exception as e:
            logger.error(f"Error migrating story {story.id}: {e}")
            return False
