import os
from ebooklib import epub
from typing import List, Dict, Optional

class EbookBuilder:
    def __init__(self):
        pass

    def make_epub(self, title: str, author: str, chapters: List[Dict[str, str]], output_path: str, cover_path: Optional[str] = None):
        """
        Generates an EPUB file from story metadata and chapter content.

        :param title: The title of the story.
        :param author: The author of the story.
        :param chapters: A list of dictionaries, each containing 'title' and 'content' keys.
        :param output_path: The path where the generated EPUB file will be saved.
        :param cover_path: (Optional) Path to the cover image file.
        """
        book = epub.EpubBook()

        # Set metadata
        book.set_identifier(title.lower().replace(' ', '_'))
        book.set_title(title)
        book.set_language('en')
        book.add_author(author)

        # Set cover if provided
        if cover_path and os.path.exists(cover_path):
            try:
                with open(cover_path, 'rb') as f:
                    cover_content = f.read()
                # Infer image type from extension
                file_name = os.path.basename(cover_path)
                book.set_cover(file_name, cover_content)
            except Exception as e:
                print(f"Warning: Could not set cover image. Error: {e}")

        # Add chapters
        epub_chapters = []
        for i, chapter_data in enumerate(chapters):
            chapter_title = chapter_data.get('title', f'Chapter {i+1}')
            chapter_content = chapter_data.get('content', '')

            # Create chapter file name
            file_name = f'chapter_{i+1}.xhtml'

            c = epub.EpubHtml(title=chapter_title, file_name=file_name, lang='en')
            c.content = f'<h1>{chapter_title}</h1>{chapter_content}'

            book.add_item(c)
            epub_chapters.append(c)

        # Define Table of Contents
        book.toc = tuple(epub_chapters)

        # Add default NCX and Nav file
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Define CSS style
        style = 'body { font-family: Times, Times New Roman, serif; }'
        nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
        book.add_item(nav_css)

        # Basic spine
        book.spine = ['nav'] + epub_chapters

        # Write to file
        try:
            epub.write_epub(output_path, book, {})
            print(f"EPUB generated at: {output_path}")
        except Exception as e:
            print(f"Error generating EPUB: {e}")
            raise e

    def compile_volume(self, story_id: int, volume_number: int) -> str:
        """
        Compiles a specific volume of a story into an EPUB.

        :param story_id: The ID of the story.
        :param volume_number: The volume number to compile.
        :return: The path to the generated EPUB file.
        """
        # Local import to avoid module-level side effects
        from database import SessionLocal, Story, Chapter

        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.id == story_id).first()
            if not story:
                raise ValueError(f"Story with ID {story_id} not found")

            chapters = session.query(Chapter).filter(
                Chapter.story_id == story_id,
                Chapter.volume_number == volume_number
            ).order_by(Chapter.index).all()

            if not chapters:
                raise ValueError(f"No chapters found for volume {volume_number} of story {story_id}")

            epub_chapters = []
            for chapter in chapters:
                if chapter.local_path and os.path.exists(chapter.local_path):
                    try:
                        with open(chapter.local_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        epub_chapters.append({'title': chapter.title, 'content': content})
                    except Exception as e:
                        print(f"Warning: Could not read chapter {chapter.title}: {e}")
                else:
                    print(f"Warning: Chapter {chapter.title} (ID: {chapter.id}) is missing content.")

            if not epub_chapters:
                raise ValueError(f"No content found for volume {volume_number}.")

            book_title = f"{story.title} - Vol {volume_number}"

            # Sanitize filename
            safe_title = "".join([c for c in book_title if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
            output_path = f"{safe_title}.epub"

            self.make_epub(book_title, story.author, epub_chapters, output_path, story.cover_path)

            return output_path

        finally:
            session.close()
