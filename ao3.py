from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from typing import List, Dict, Optional
import re

from core_logic import BaseSource
from polite_requester import PoliteRequester

class AO3Source(BaseSource):
    BASE_URL = "https://archiveofourown.org"

    def __init__(self):
        self.requester = PoliteRequester()

    def identify(self, url: str) -> bool:
        return 'archiveofourown.org' in url

    def get_metadata(self, url: str) -> Dict:
        response = self.requester.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Title
        title_tag = soup.select_one('h2.title.heading')
        title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

        # Author
        author_tag = soup.select_one('h3.byline.heading')
        author = "Unknown Author"
        if author_tag:
            author_links = author_tag.find_all('a', href=True)
            if author_links:
                author = ", ".join([a.get_text(strip=True) for a in author_links])
            else:
                author = author_tag.get_text(strip=True)

        # Description
        description_div = soup.select_one('blockquote.userstuff.summary')
        description = description_div.get_text("\n", strip=True) if description_div else "No description available."

        # Cover (AO3 doesn't have standard covers, leaving None)
        cover_url = None

        # Tags
        tags = []
        # Fandoms
        for t in soup.select('dd.fandom.tags li a.tag'):
            tags.append(t.get_text(strip=True))

        # Freeform (Additional Tags)
        for t in soup.select('dd.freeform.tags li a.tag'):
            tags.append(t.get_text(strip=True))

        # Rating
        rating = None
        rating_tag = soup.select_one('dd.rating.tags li a.tag')
        if rating_tag:
            rating = rating_tag.get_text(strip=True)

        # Language
        language = "English"
        language_dd = soup.select_one('dd.language')
        if language_dd:
            language = language_dd.get_text(strip=True)

        # Status
        publication_status = "Unknown"
        chapters_dd = soup.select_one('dd.chapters')
        if chapters_dd:
            chapter_text = chapters_dd.get_text(strip=True)
            # Format: "X/Y" or "X/?"
            if '/' in chapter_text:
                current, total = chapter_text.split('/', 1)
                if total == '?':
                    publication_status = "Ongoing"
                elif current == total:
                    publication_status = "Completed"
                else:
                    publication_status = "Ongoing"

        # Sometimes stats has "Completed: YYYY-MM-DD"
        status_dt = soup.find('dt', class_='status')
        if status_dt and 'Completed' in status_dt.get_text(strip=True):
             publication_status = "Completed"

        return {
            'title': title,
            'author': author,
            'description': description,
            'cover_url': cover_url,
            'tags': ", ".join(tags) if tags else None,
            'rating': rating,
            'language': language,
            'publication_status': publication_status
        }

    def get_chapter_list(self, url: str) -> List[Dict]:
        # Handle /chapters/ urls by converting to work url
        work_id_match = re.search(r'/works/(\d+)', url)
        if not work_id_match:
             return []

        work_id = work_id_match.group(1)
        navigate_url = f"{self.BASE_URL}/works/{work_id}/navigate"

        # We need to be careful. If the work is locked, we might get a redirect to login.
        # PoliteRequester raises error on bad status, but redirect to login is usually 302 then 200.
        # But we assume public works for now.

        response = self.requester.get(navigate_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        chapters = []
        # AO3 navigate page lists chapters in an ordered list
        chapter_list = soup.select('ol.chapter.index li')

        if chapter_list:
            for li in chapter_list:
                link = li.find('a', href=True)
                if link:
                    title = link.get_text(strip=True)
                    chapter_url = urljoin(self.BASE_URL, link['href'])

                    chapters.append({
                        'title': title,
                        'url': chapter_url
                    })

        if not chapters:
            # Fallback: assume single chapter work or navigation page failed (e.g. oneshot)
            # Fetch the work page to check
            work_url = f"https://archiveofourown.org/works/{work_id}"
            # We avoid fetching if we already fetched for metadata, but we don't share state here easily.
            # Assuming single chapter.

            # Use metadata title if possible, but we need to fetch it to be sure.
            # For efficiency, let's just use "Chapter 1" or fetch metadata.
            # Let's fetch metadata to get the title.

            # Wait, if we are calling get_chapter_list, we probably already called get_metadata or will.
            # But here we need to return a list.

            # Let's try to fetch the work page to confirm it exists and get title.
            try:
                metadata = self.get_metadata(work_url)
                chapters.append({
                    'title': metadata.get('title', 'Chapter 1'),
                    'url': work_url
                })
            except Exception:
                pass

        return chapters

    def get_chapter_content(self, chapter_url: str) -> str:
        response = self.requester.get(chapter_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Content is usually in <div id="chapters" class="userstuff">
        # Or <div class="userstuff"> inside a chapter container.

        # In multi-chapter view, #chapters contains multiple divs?
        # No, when viewing a single chapter (which we do by url), it shows that chapter.

        content_div = soup.select_one('div#chapters div.userstuff')
        if not content_div:
             content_div = soup.select_one('div#chapters')
        if not content_div:
            content_div = soup.select_one('div.userstuff')

        if content_div:
            # Remove scripts and styles
            for tag in content_div(['script', 'style']):
                tag.decompose()

            # AO3 specific cleanup
            # Remove "Chapter Text" heading if present inside
            h3 = content_div.find('h3', string="Chapter Text")
            if h3:
                h3.decompose()

            # Remove "Chapter X" link/heading that might appear at top

            return content_div.decode_contents()

        return ""

    def set_config(self, config: Dict):
        if not config:
            return

        # Look for cookies
        cookies = {}
        # Try 'cookies' key first (JSON object)
        c = config.get('cookies')
        if c:
            if isinstance(c, dict):
                cookies = c
            elif isinstance(c, str):
                # Try to parse string "key=value; key2=value2"
                try:
                    for pair in c.split(';'):
                        if '=' in pair:
                            k, v = pair.strip().split('=', 1)
                            cookies[k] = v
                except Exception:
                    pass

        if cookies:
            self.requester.set_cookies(cookies)

    def search(self, query: str) -> List[Dict]:
        encoded_query = quote(query)
        url = f"{self.BASE_URL}/works/search?work_search[query]={encoded_query}"

        try:
            response = self.requester.get(url)
        except Exception as e:
            # Check for Cloudflare/Auth errors
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code in [403, 503]:
                    print(f"AO3 Search blocked (Status {e.response.status_code}). Check cookies.")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('li.work.blurb'):
            # Title
            title_tag = item.select_one('h4.heading a[href^="/works/"]')
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            story_url = urljoin(self.BASE_URL, title_tag['href'])

            # Author
            author_tag = item.select_one('h4.heading a[rel="author"]')
            author = "Anonymous"
            if author_tag:
                 author = author_tag.get_text(strip=True)
            else:
                 h4 = item.select_one('h4.heading')
                 if h4 and "Anonymous" in h4.get_text():
                     author = "Anonymous"

            results.append({
                'title': title,
                'url': story_url,
                'author': author,
                'cover_url': None,
                'provider': 'Archive of Our Own'
            })

        return results
