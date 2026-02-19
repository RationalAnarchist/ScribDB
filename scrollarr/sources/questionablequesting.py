from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict
import re
from datetime import datetime

from .templates.forum import XenForoSource

class QuestionableQuestingSource(XenForoSource):
    BASE_URL = "https://forum.questionablequesting.com"
    key = "questionablequesting"
    name = "Questionable Questing"

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

class QuestionableQuestingAllPostsSource(QuestionableQuestingSource):
    """
    Variant of QQ Source that fetches ALL author posts from the thread,
    using threadmarks only as section dividers.
    """
    key = "questionablequesting_all"
    name = "Questionable Questing (All Posts)"

    def identify(self, url: str) -> bool:
        # We don't want to auto-identify with this, as it's a special mode
        return False

    def _extract_post_id(self, url: str) -> str:
        # post-1234 or posts/1234
        match = re.search(r'post-(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'posts/(\d+)', url)
        if match:
            return match.group(1)
        return ""

    def get_chapter_list(self, url: str, **kwargs) -> List[Dict]:
        url = self._normalize_url(url)

        # 1. Fetch Threadmarks to get Volumes
        # This reuses the base class implementation which fetches from /threadmarks
        tm_list = super().get_chapter_list(url)

        # Map Post ID -> (Volume Title, Volume Number)
        # Note: Threadmarks might not be in chronological order of post IDs if the author reordered them.
        # But usually they are. We use the ORDER in threadmarks list as Volume Number.
        threadmarks_map = {}
        for i, tm in enumerate(tm_list):
            post_id = self._extract_post_id(tm['url'])
            if post_id:
                threadmarks_map[post_id] = (tm['title'], i + 1)

        # 2. Get Metadata for Author Name
        meta = self.get_metadata(url)
        author_name = meta['author']

        # 3. Crawl Thread Pages
        chapters = []
        next_url = url # Start at page 1

        # Tracking state
        current_vol_title = "Prologue"
        current_vol_number = 1
        part_counter = 0

        # Optimization: Start from Last Known Chapter if available
        last_chapter = kwargs.get('last_chapter')
        if last_chapter and last_chapter.get('url'):
            try:
                # Determine start page from last chapter URL
                # Fetching the post URL usually redirects to the thread page with page-XX
                # We use a HEAD request to follow redirects efficiently, or GET if HEAD not supported well
                resp = self.requester.get(last_chapter['url'], allow_redirects=True)
                final_url = resp.url

                # Check for page number in URL
                # e.g. threads/slug.123/page-81 or page-81#post-1234
                match = re.search(r'page-(\d+)', final_url)
                if match:
                    # Construct clean page URL
                    # Use the final_url but strip anchor and ensure it is just the page
                    page_base = final_url.split('#')[0]
                    next_url = page_base

                    # Initialize state from last_chapter to be safe
                    # This will be corrected when we hit the actual post in the loop
                    if last_chapter.get('volume_title'):
                        current_vol_title = last_chapter['volume_title']
                    if last_chapter.get('volume_number'):
                        current_vol_number = last_chapter['volume_number']

                    # Try to parse part counter from title
                    # Format: "{vol} - Part {X}"
                    title = last_chapter.get('title', '')
                    # Escape volume title for regex
                    vol_esc = re.escape(current_vol_title)
                    part_match = re.search(rf"{vol_esc} - Part (\d+)", title)
                    if part_match:
                        part_counter = int(part_match.group(1))
                    elif title == current_vol_title:
                         # Last chapter was a threadmark
                         part_counter = 1
            except Exception:
                # Fallback to page 1 if anything fails
                pass

        # Optimization: We need to know if we are "inside" a volume.
        # If the first post is NOT a threadmark, it's Prologue (Vol 1).
        # The user said "threadmarks to indicate the start of each section".
        # So we update current_vol when we hit a threadmark post.

        # Initialize global index
        current_global_index = 0
        found_sync_point = False

        if last_chapter and last_chapter.get('index'):
            current_global_index = last_chapter.get('index')
        else:
            # If no last chapter, we start from beginning
            found_sync_point = True

        while next_url:
            response = self.requester.get(next_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all posts
            # XenForo 2: article.message--post
            # Also handle older XenForo or structure variations if needed, but standard is message--post
            posts = soup.select('.message--post')

            # Some threads might embed the first post in a different container if it's the OP?
            # Usually OP is just the first message--post.

            for post in posts:
                # Get Post ID
                # data-content="post-1234"
                post_id_attr = post.get('data-content', '')
                post_id = post_id_attr.replace('post-', '')
                if not post_id:
                    continue

                # Check Author
                # .message-userDetails .username
                user_tag = post.select_one('.message-userDetails .username')
                if not user_tag:
                    # Fallback: sometimes user details are hidden or structure is different
                    continue

                post_author = user_tag.get_text(strip=True)

                # Check if it's the author
                if post_author != author_name:
                    continue

                # It is an author post.

                # URL
                # Construct permalink
                chapter_url = urljoin(self.BASE_URL, f"posts/{post_id}/")

                # Determine if we process this post (Sync Logic)
                is_sync_post = False
                if last_chapter and not found_sync_point:
                    if chapter_url == last_chapter.get('url'):
                        found_sync_point = True
                        is_sync_post = True
                    else:
                        # Skip this post as we haven't reached the sync point yet
                        continue
                else:
                    # Normal processing
                    current_global_index += 1

                # Sync state if we hit the last known chapter
                if is_sync_post:
                    # Force sync state
                    if last_chapter.get('volume_title'):
                        current_vol_title = last_chapter['volume_title']
                    if last_chapter.get('volume_number'):
                        current_vol_number = last_chapter['volume_number']
                    if last_chapter.get('index'):
                        current_global_index = last_chapter.get('index')

                    # Parse title to sync part_counter
                    title = last_chapter.get('title', '')
                    if title == current_vol_title:
                        part_counter = 1
                    else:
                        vol_esc = re.escape(current_vol_title)
                        part_match = re.search(rf"{vol_esc} - Part (\d+)", title)
                        if part_match:
                            # We subtract 1 because the loop logic will increment it for the *current* post
                            part_counter = int(part_match.group(1)) - 1

                # Is it a threadmark?
                if post_id in threadmarks_map:
                    tm_title, tm_number = threadmarks_map[post_id]

                    current_vol_title = tm_title
                    current_vol_number = tm_number
                    part_counter = 1 # Reset counter (1 means the TM post itself)

                    chapter_title = tm_title
                else:
                    # Not a threadmark.
                    # If this is the FIRST post and it's NOT a threadmark, it's definitely Prologue part 1.
                    if part_counter == 0:
                        part_counter = 1
                    else:
                        part_counter += 1

                    chapter_title = f"{current_vol_title} - Part {part_counter}"

                # Date
                published_date = None
                time_tag = post.select_one('time')
                if time_tag:
                    try:
                        if time_tag.has_attr('data-time'):
                            timestamp = float(time_tag['data-time'])
                            published_date = datetime.fromtimestamp(timestamp)
                        elif time_tag.has_attr('datetime'):
                            published_date = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))
                    except Exception:
                        pass

                chapters.append({
                    'title': chapter_title,
                    'url': chapter_url,
                    'published_date': published_date,
                    'volume_title': current_vol_title,
                    'volume_number': current_vol_number,
                    'index': current_global_index
                })

            # Find next page
            next_link = soup.select_one('a.pageNav-jump--next')
            if next_link:
                next_url = urljoin(self.BASE_URL, next_link['href'])
            else:
                next_url = None

        return chapters
