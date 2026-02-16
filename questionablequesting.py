from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from typing import List, Dict
import re
from datetime import datetime

from core_logic import BaseSource
from polite_requester import PoliteRequester

class QuestionableQuestingSource(BaseSource):
    BASE_URL = "https://forum.questionablequesting.com"

    def __init__(self):
        self.requester = PoliteRequester()

    def identify(self, url: str) -> bool:
        return 'questionablequesting.com/threads/' in url

    def _normalize_url(self, url: str) -> str:
        """
        Normalizes the URL to the base thread URL.
        Handles RSS feeds (threadmarks.rss) and page numbers.
        """
        # Regex to find the base thread URL: threads/slug.id/
        # Matches: .../threads/story-name.1234/ and .../threads/story-name.1234
        match = re.search(r'(https?://forum\.questionablequesting\.com/threads/[^/]+\.\d+)', url)
        if match:
            return match.group(1) + '/'
        return url

    def get_metadata(self, url: str) -> Dict:
        url = self._normalize_url(url)
        response = self.requester.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Title
        title_tag = soup.find('h1', class_='p-title-value')
        title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

        # Author - usually in the "Thread starter" part or first post
        author = "Unknown Author"
        # Try finding thread starter from metadata
        # XenForo 2 usually has a structured data or meta tags
        author_tag = soup.select_one('.p-description a.username')
        if not author_tag:
             # Try first post
             first_post = soup.select_one('.message-userDetails .username')
             if first_post:
                 author_tag = first_post

        if author_tag:
            author = author_tag.get_text(strip=True)

        # Description
        # Use meta description or first post snippet
        description = "No description available."
        og_desc = soup.find('meta', property='og:description')
        if og_desc:
            description = og_desc.get('content', description)

        # Tags
        tags = []
        tag_list = soup.select('.tagList .tagItem')
        for tag in tag_list:
            tags.append(tag.get_text(strip=True))

        # Status
        status = "Unknown"
        # Check for prefixes like [Complete] or [Ongoing] in title or prefix tags
        prefix_tag = soup.select_one('.labelLink')
        if prefix_tag:
             status_text = prefix_tag.get_text(strip=True)
             if 'Complete' in status_text:
                 status = 'Completed'
             elif 'Ongoing' in status_text:
                 status = 'Ongoing'

        # Cover URL
        # QQ doesn't enforce covers. Maybe use user avatar or check first post for img?
        # For now, generic or None.
        cover_url = None

        return {
            'title': title,
            'author': author,
            'description': description,
            'cover_url': cover_url,
            'tags': ", ".join(tags) if tags else None,
            'rating': None, # QQ doesn't have a standard rating system accessible easily
            'language': 'English',
            'publication_status': status
        }

    def get_chapter_list(self, url: str) -> List[Dict]:
        url = self._normalize_url(url)
        # Construct threadmarks URL
        threadmarks_url = urljoin(url, 'threadmarks')

        chapters = []
        next_url = threadmarks_url

        while next_url:
            response = self.requester.get(next_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Parse chapters
            # Look for threadmark items
            items = soup.select('.structItem--threadmark')
            for item in items:
                link = item.select_one('.structItem-title a')
                if link:
                    title = link.get_text(strip=True)
                    chapter_url = urljoin(self.BASE_URL, link['href'])

                    # Date
                    published_date = None
                    time_tag = item.select_one('time')
                    if time_tag:
                        try:
                            # XenForo time tags usually have data-time or datetime
                            if time_tag.has_attr('data-time'):
                                timestamp = float(time_tag['data-time'])
                                published_date = datetime.fromtimestamp(timestamp)
                            elif time_tag.has_attr('datetime'):
                                published_date = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))
                        except Exception:
                            pass

                    chapters.append({
                        'title': title,
                        'url': chapter_url,
                        'published_date': published_date
                    })

            # Find next page
            next_link = soup.select_one('a.pageNav-jump--next')
            if next_link:
                next_url = urljoin(self.BASE_URL, next_link['href'])
            else:
                next_url = None

        return chapters

    def get_chapter_content(self, chapter_url: str) -> str:
        response = self.requester.get(chapter_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # We need to find the specific post content.
        # The URL usually has a hash like #post-123 or ends in posts/123/
        # Or it might be a permalink.
        # XenForo permalinks redirect to the thread page with an anchor.

        # If we are on the page, we need to find the post that matches.
        # However, `chapter_url` from threadmarks usually points to the specific post.
        # e.g. threads/.../post-1234
        # This page usually highlights the post or anchors to it.

        # Strategy: Look for the post that is marked as the target, or if ambiguous, take the first post on page that matches ID?
        # Actually, if we fetch the permalink, XenForo usually renders the thread page positioned at the post.
        # But we need to EXTRACT just that post.

        # Attempt to extract post ID from URL
        post_id_match = re.search(r'post-(\d+)', chapter_url)
        if not post_id_match:
             # Try other format posts/1234
             post_id_match = re.search(r'posts/(\d+)', chapter_url)

        content_div = None

        if post_id_match:
            post_id = post_id_match.group(1)
            # Find article/div with id js-post-{post_id}
            post_container = soup.find(id=f"js-post-{post_id}")
            if post_container:
                content_div = post_container.select_one('.bbWrapper')

        # Fallback: if we can't match ID (maybe URL format changed), try finding the "highlighted" post
        if not content_div:
             # Check for message-content in the first message?
             # Or maybe look for the threadmark header label inside the post?
             # Let's try finding the first bbWrapper
             content_div = soup.select_one('.bbWrapper')

        if content_div:
            # Cleanup
            # Remove scripts, styles
            for tag in content_div(['script', 'style']):
                tag.decompose()

            # Remove quotes? Maybe not, story might have dialogue.
            # Remove 'Click to expand' text in quotes if present (XenForo quote expansion)
            for tag in content_div.select('.bbCodeBlock-expandLink'):
                tag.decompose()

            return content_div.decode_contents()

        return ""

    def search(self, query: str) -> List[Dict]:
        # Basic search implementation
        # /search/search?keywords={query}&title_only=1
        search_url = f"{self.BASE_URL}/search/search?keywords={quote_plus(query)}&title_only=1"

        # XenForo might require a POST or might redirect. Requests handles redirects.
        response = self.requester.get(search_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        # Results are usually in ol.block-body with li.block-row
        rows = soup.select('.block-row')

        for row in rows:
            title_link = row.select_one('.contentRow-title a')
            if not title_link:
                continue

            title = title_link.get_text(" ", strip=True)
            url = urljoin(self.BASE_URL, title_link['href'])

            # Ensure it's a thread
            if '/threads/' not in url:
                continue

            # Clean URL (remove /post-xyz etc if present, though search usually links to thread or post)
            # If it links to a post, we might want to strip it to thread URL
            # But identify() needs to work. identify works on /threads/

            # Author
            author = "Unknown"
            author_link = row.select_one('.contentRow-minor a.username') # Or just a
            if author_link:
                author = author_link.get_text(strip=True)

            # Snippet
            snippet = ""
            snippet_div = row.select_one('.contentRow-snippet')
            if snippet_div:
                snippet = snippet_div.get_text(strip=True)

            # De-duplicate by URL/Thread ID?
            # Ideally handled by caller, but we can check if we already added this thread ID.

            results.append({
                'title': title,
                'url': url,
                'author': author,
                'description': snippet,
                'provider': 'Questionable Questing'
            })

        return results
