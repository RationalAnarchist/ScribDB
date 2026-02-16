import os
import shutil
from ebooklib import epub
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re

# ReportLab imports for PDF generation
try:
    from reportlab.lib.pagesizes import A4, LETTER, A5, LEGAL, B5
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as ReportLabImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
    from reportlab.lib.units import inch
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    print("Warning: ReportLab not installed. PDF generation will be disabled.")

class EbookBuilder:
    def __init__(self):
        pass

    def make_epub(self, title: str, author: str, chapters: List[Dict[str, str]], output_path: str, cover_path: Optional[str] = None, css: Optional[str] = None):
        """
        Generates an EPUB file from story metadata and chapter content.
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
        style = css if css else 'body { font-family: Times, Times New Roman, serif; }'
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

    def make_pdf(self, title: str, author: str, chapters: List[Dict[str, str]], output_path: str, cover_path: Optional[str] = None, css: Optional[str] = None, page_size: str = 'A4'):
        """
        Generates a PDF file using ReportLab.
        """
        if not HAS_REPORTLAB:
            raise ImportError("ReportLab is not installed. Cannot generate PDF.")

        # Determine page size
        size_map = {
            'A4': A4,
            'LETTER': LETTER,
            'A5': A5,
            'LEGAL': LEGAL,
            'B5': B5,
            '6X9': (6 * inch, 9 * inch),
            '5X8': (5 * inch, 8 * inch)
        }

        ps = size_map.get(page_size.upper(), A4)

        doc = SimpleDocTemplate(output_path, pagesize=ps,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)

        Story = []
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
        styles.add(ParagraphStyle(name='ChapterTitle', parent=styles['Heading1'], alignment=TA_CENTER, spaceAfter=20))

        # Title Page
        if cover_path and os.path.exists(cover_path):
            try:
                # Add cover image scaled to fit page width roughly
                im = ReportLabImage(cover_path, width=400, height=600, kind='proportional') # Basic scaling
                Story.append(im)
                Story.append(PageBreak())
            except Exception as e:
                print(f"Warning: Could not add cover to PDF: {e}")

        Story.append(Paragraph(title, styles['Title']))
        Story.append(Spacer(1, 12))
        Story.append(Paragraph(f"By {author}", styles['Normal']))
        Story.append(PageBreak())

        # Chapters
        for i, chapter_data in enumerate(chapters):
            chapter_title = chapter_data.get('title', f'Chapter {i+1}')
            chapter_content = chapter_data.get('content', '')

            # Add Chapter Title
            Story.append(Paragraph(chapter_title, styles['ChapterTitle']))

            # Parse HTML content
            # We use BeautifulSoup to extract text and basic formatting
            soup = BeautifulSoup(chapter_content, 'html.parser')

            # Simple conversion: Iterate over p tags
            # ReportLab Paragraph supports simple XML-like tags: b, i, u, strike, super, sub
            # We need to sanitize the content to only allow these.

            elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'div', 'br'])

            if not elements:
                # If no structure found, just dump text
                text = soup.get_text()
                # Sanitize text for XML (escape & < >)
                from xml.sax.saxutils import escape
                safe_text = escape(text)
                Story.append(Paragraph(safe_text, styles['Justify']))
                Story.append(Spacer(1, 12))
            else:
                for element in elements:
                    if element.name == 'br':
                        Story.append(Spacer(1, 12))
                        continue

                    # Extract text with allowed tags
                    # This is a complex problem. For now, we take .decode_contents() and regex replace disallowed tags?
                    # Or just get_text() and lose formatting?
                    # Better: keep <b> <i> etc.

                    # Convert internal tags to reportlab tags
                    # element.decode_contents() might return <b>Text</b> which is fine.
                    # But <span class="..."> needs to be removed.
                    # Let's try to just clean it.

                    # Very basic cleaner
                    raw_html = str(element)
                    clean_text = self._clean_html_for_pdf(raw_html)

                    if element.name in ['h1', 'h2', 'h3']:
                        style = styles['Heading2']
                    else:
                        style = styles['Justify']

                    try:
                        p = Paragraph(clean_text, style)
                        Story.append(p)
                        Story.append(Spacer(1, 12))
                    except Exception as e:
                        # Fallback if XML parsing fails
                        print(f"Warning: PDF Paragraph error: {e}")
                        safe_text = element.get_text()
                        Story.append(Paragraph(safe_text, style))
                        Story.append(Spacer(1, 12))

            Story.append(PageBreak())

        try:
            doc.build(Story)
            print(f"PDF generated at: {output_path}")
        except Exception as e:
            print(f"Error generating PDF: {e}")
            raise e

    def _clean_html_for_pdf(self, html_str: str) -> str:
        """
        Cleans HTML to be compatible with ReportLab Paragraphs.
        Keeps <b>, <i>, <u>. Removes others.
        """
        # Remove wrapper tag (e.g. <p>...</p>)
        # Regex to match start tag and end tag
        content = re.sub(r'^<[^>]+>', '', html_str)
        content = re.sub(r'</[^>]+>$', '', content)

        # Allowed tags in ReportLab: b, i, u, strike, super, sub, font, br
        # We replace everything else.

        # 1. Unescape entities (ReportLab handles some, but be safe)
        # Actually ReportLab needs XML entities.

        # Strategy: BeautifulSoup get_text() is too aggressive.
        # Let's use regex to remove attributes from tags
        content = re.sub(r'<([a-z][a-z0-9]*)[^>]*>', r'<\1>', content)

        # Replace <strong> with <b>, <em> with <i>
        content = content.replace('<strong>', '<b>').replace('</strong>', '</b>')
        content = content.replace('<em>', '<i>').replace('</em>', '</i>')

        # Remove tags that are not allowed
        allowed = ['b', 'i', 'u', 'strike', 'super', 'sub', 'br']

        def replace_tag(match):
            tag = match.group(1)
            is_close = match.group(0).startswith('</')
            if tag == 'br':
                return '<br/>'
            if tag in allowed:
                return match.group(0)
            return '' # Strip other tags

        content = re.sub(r'</?([a-z]+)[^>]*>', replace_tag, content)

        # Clean up double spaces etc
        content = content.strip()
        return content

    def compile_volume(self, story_id: int, volume_number: int) -> str:
        """
        Compiles a specific volume of a story.
        Respects the story's profile output format.
        """
        # Local import to avoid module-level side effects
        from database import SessionLocal, Story, Chapter
        from config import config_manager

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

            # Use volume title if available in the first chapter
            volume_title = chapters[0].volume_title
            suffix = volume_title if volume_title else f"Vol {volume_number}"

            return self._compile_chapters(story, chapters, suffix)

        finally:
            session.close()

    def compile_full_story(self, story_id: int) -> str:
        """
        Compiles the entire story into a single book.
        """
        from database import SessionLocal, Story, Chapter

        session = SessionLocal()
        try:
            story = session.query(Story).filter(Story.id == story_id).first()
            if not story:
                raise ValueError(f"Story with ID {story_id} not found")

            chapters = session.query(Chapter).filter(
                Chapter.story_id == story_id
            ).order_by(Chapter.volume_number, Chapter.index).all()

            if not chapters:
                raise ValueError(f"No chapters found for story {story_id}")

            return self._compile_chapters(story, chapters, "Full")

        finally:
            session.close()

    def _compile_chapters(self, story, chapters, suffix: str) -> str:
        """
        Internal method to compile a list of chapters based on story profile.
        """
        from config import config_manager

        # Prepare content
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
            raise ValueError(f"No content found for {suffix}.")

        book_title = f"{story.title} - {suffix}"

        # Get library path and pattern
        library_path = config_manager.get('library_path', 'library')
        filename_pattern = config_manager.get('filename_pattern', '{Title} - {Volume}')

        # Determine Format
        output_format = 'epub'
        if story.profile:
            output_format = story.profile.output_format.lower()

        # Create filename
        filename = filename_pattern.replace('{Title}', story.title)\
                                   .replace('{Author}', story.author)\
                                   .replace('{Volume}', suffix)

        # Sanitize filename
        safe_filename = "".join([c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')]).strip()

        # Ensure extension matches format
        if not safe_filename.lower().endswith(f".{output_format}"):
            safe_filename += f".{output_format}"

        # Ensure directory exists
        if not os.path.exists(library_path):
            try:
                os.makedirs(library_path)
            except Exception as e:
                print(f"Error creating library directory: {e}")

        output_path = os.path.join(library_path, safe_filename)

        # Get profile CSS
        profile_css = None
        if story.profile and story.profile.css:
                profile_css = story.profile.css

        # Dispatch
        if output_format == 'pdf':
            page_size = 'A4'
            if story.profile and story.profile.pdf_page_size:
                page_size = story.profile.pdf_page_size
            self.make_pdf(book_title, story.author, epub_chapters, output_path, story.cover_path, css=profile_css, page_size=page_size)
        else:
            self.make_epub(book_title, story.author, epub_chapters, output_path, story.cover_path, css=profile_css)

        return output_path
