import re
import time
import subprocess
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from ..core_logic import BaseSource

class KemonoSource(BaseSource):
    BASE_URLS = ["https://kemono.su", "https://kemono.party", "https://kemono.cr"]

    def identify(self, url: str) -> bool:
        return any(base in url for base in self.BASE_URLS)

    def _get_playwright(self):
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright()
        except ImportError:
            raise ImportError("Playwright is not installed. Please install it to use Kemono source.")

    def _ensure_browser_installed(self):
        """Attempts to install Playwright browsers if missing."""
        print("Playwright browsers not found. Installing...")
        try:
            subprocess.run(["playwright", "install", "chromium"], check=True)
            print("Playwright browsers installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Playwright browsers: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error installing Playwright browsers: {e}")
            raise

    def _scrape_page(self, url: str):
        """Helper to scrape a page using Playwright."""
        with self._get_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    self._ensure_browser_installed()
                    browser = p.chromium.launch(headless=True)
                else:
                    raise e

            page = browser.new_page()
            try:
                # Set a reasonable timeout
                page.set_default_timeout(60000)

                # Navigate
                response = page.goto(url, wait_until="domcontentloaded")

                # Check for cloudflare or other blocks?
                # Usually just waiting for selector works better.
                # But here we just want the content.

                # Wait a bit for JS to execute if needed
                page.wait_for_timeout(2000)

                content = page.content()
                return content
            finally:
                browser.close()

    def get_metadata(self, url: str) -> Dict:
        html = self._scrape_page(url)
        soup = BeautifulSoup(html, 'html.parser')

        # Title is usually the artist name
        # Typically in <h1 class="user-header__name">Artist Name</h1>
        # Or <meta property="og:title" content="...">

        title_tag = soup.select_one('h1.user-header__name span') or soup.select_one('meta[property="og:title"]')
        title = "Unknown Title"
        if title_tag:
            if title_tag.name == 'meta':
                title = title_tag.get('content', 'Unknown Title')
            else:
                title = title_tag.get_text(strip=True)

        # Author is the same as title usually for artist pages
        author = title

        # Description
        description = "No description available."
        # Sometimes user profile has description? usually not prominent.

        # Cover
        # <div class="user-header__avatar"> <img src="..."> </div>
        cover_url = None
        avatar_img = soup.select_one('.user-header__avatar img')
        if avatar_img:
            src = avatar_img.get('src')
            if src:
                if src.startswith('//'):
                    cover_url = f"https:{src}"
                elif src.startswith('/'):
                    cover_url = f"https://kemono.su{src}" # Defaulting to .su if relative, but maybe check url
                else:
                    cover_url = src

        return {
            'title': title,
            'author': author,
            'description': description,
            'cover_url': cover_url,
            'tags': None,
            'rating': None,
            'language': 'English', # Assumption
            'publication_status': 'Ongoing'
        }

    def get_chapter_list(self, url: str, **kwargs) -> List[Dict]:
        chapters = []
        offset = 0
        has_more = True

        # Determine base URL for pagination
        base_url = url.split('?')[0]

        # We need a robust way to iterate pages.
        # Using a single browser session is better for multiple pages.

        with self._get_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    self._ensure_browser_installed()
                    browser = p.chromium.launch(headless=True)
                else:
                    raise e

            context = browser.new_context()
            page = context.new_page()

            try:
                while has_more:
                    page_url = f"{base_url}?o={offset}"
                    print(f"Scraping list page: {page_url}")

                    try:
                        page.goto(page_url, timeout=60000, wait_until="domcontentloaded")
                        page.wait_for_selector('.card-list__items', timeout=10000)
                    except Exception as e:
                        print(f"Error loading page {page_url}: {e}")
                        break

                    # Get page content
                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')

                    posts = soup.select('.card-list__items .post-card')
                    if not posts:
                        has_more = False
                        break

                    page_chapters = []
                    for post in posts:
                        link_tag = post.select_one('a')
                        if not link_tag:
                            continue

                        href = link_tag.get('href')
                        if not href:
                            continue

                        # Resolve URL
                        full_url = href
                        if href.startswith('/'):
                            full_url = f"https://kemono.su{href}" # default to .su

                        # Title
                        title_div = post.select_one('.post-card__header')
                        title = title_div.get_text(strip=True) if title_div else "Untitled"

                        # Date
                        date_div = post.select_one('.post-card__footer div')
                        published_date = None
                        if date_div:
                            # Format usually "2023-01-01 12:00:00" or similar
                            date_str = date_div.get_text(strip=True)
                            try:
                                # Try parsing ISO format or variations
                                # Often displayed as "Added: YYYY-MM-DD" or just date
                                # Actually Kemono displays "Published: YYYY-MM-DD"
                                # Let's try basic parsing
                                if 'Published:' in date_str:
                                    date_str = date_str.replace('Published:', '').strip()

                                published_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                try:
                                    published_date = datetime.strptime(date_str, "%Y-%m-%d")
                                except:
                                    pass

                        page_chapters.append({
                            'title': title,
                            'url': full_url,
                            'published_date': published_date
                        })

                    if not page_chapters:
                        has_more = False
                    else:
                        chapters.extend(page_chapters)
                        offset += 25 # Standard offset

                        # Safety break
                        if offset > 5000: # Limit to 200 pages
                            print("Reached page limit for safety.")
                            has_more = False

                        # Slight delay
                        time.sleep(1)

            finally:
                browser.close()

        # Sort by date if possible, but they come ordered by date desc usually.
        # We return them in the order we found them (usually newest first).
        # StoryManager handles ordering/indexing.
        return chapters

    def get_chapter_content(self, chapter_url: str) -> str:
        output = []

        # Using the logic from sample file, adapted to class method
        with self._get_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    self._ensure_browser_installed()
                    browser = p.chromium.launch(headless=True)
                else:
                    raise e

            page = browser.new_page()
            try:
                page.goto(chapter_url, timeout=90000, wait_until="domcontentloaded")

                try:
                    page.wait_for_selector('.post__content, .post-content', timeout=20000)
                except:
                    print(f"Timeout waiting for content on {chapter_url}")

                content_html = ""
                content_el = page.query_selector('.post__content')
                if not content_el:
                    content_el = page.query_selector('.post-content')

                if content_el:
                    content_html = content_el.inner_html()

                attachments_html = ""

                # Check for main file
                thumb_el = page.query_selector('.post__thumbnail img')
                if thumb_el:
                    src = thumb_el.get_attribute('src')
                    if src:
                        if src.startswith('/'):
                            src = f"https://kemono.su{src}"
                        attachments_html += f'<img src="{src}" /><br/>'

                # Check for attachments
                atts = page.query_selector_all('.post__attachment a')
                for att in atts:
                    href = att.get_attribute('href')
                    thumb = att.query_selector('.post__attachment-thumb')

                    if thumb:
                        src = thumb.get_attribute('src')
                        if src:
                            if src.startswith('/'):
                                src = f"https://kemono.su{src}"
                            attachments_html += f'<img src="{src}" /><br/>'
                    elif href and (href.endswith('.jpg') or href.endswith('.png') or href.endswith('.jpeg')):
                        if href.startswith('/'):
                            href = f"https://kemono.su{href}"
                        attachments_html += f'<img src="{href}" /><br/>'

                if content_html:
                    output.append(content_html)

                if attachments_html:
                    output.append(attachments_html)

                if not output:
                    return "<p>Content not found.</p>"

                return "".join(output)

            finally:
                browser.close()

    def search(self, query: str) -> List[Dict]:
        """
        Searches for artists on Kemono.
        """
        results = []
        search_url = f"https://kemono.cr/artists?q={query}" # Default to .cr as it seems more stable

        with self._get_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    self._ensure_browser_installed()
                    browser = p.chromium.launch(headless=True)
                else:
                    raise e

            page = browser.new_page()
            try:
                page.set_default_timeout(60000)
                # print(f"Searching Kemono: {search_url}")
                page.goto(search_url, wait_until="domcontentloaded")

                # Wait for content or timeout
                try:
                    # Wait for results container or empty state
                    page.wait_for_selector('.card-list__items', timeout=10000)
                except:
                    # Might be empty or slow
                    pass

                # Allow JS to render items
                page.wait_for_timeout(2000)

                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

                # Items are usually <a> tags inside .card-list__items
                # Structure: <a href="/service/user/id" ...> ... <div class="user-card__name">Name</div> ... <div class="user-card__service">Service</div> ... </a>
                items = soup.select('.card-list__items a')

                for item in items:
                    href = item.get('href')
                    if not href:
                        continue

                    full_url = href
                    if href.startswith('/'):
                        full_url = f"https://kemono.cr{href}"

                    name_div = item.select_one('.user-card__name')
                    name = name_div.get_text(strip=True) if name_div else "Unknown"

                    service_div = item.select_one('.user-card__service')
                    service = service_div.get_text(strip=True) if service_div else "Unknown Service"

                    # Cover/Avatar
                    # <div class="user-card__header" style="background-image: url(...)">
                    # or img inside? Inspecting usually shows background-image on header
                    cover_url = None
                    header_div = item.select_one('.user-card__header')
                    if header_div and header_div.has_attr('style'):
                        style = header_div['style']
                        # Extract url('...')
                        match = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", style)
                        if match:
                            src = match.group(1)
                            if src.startswith('/'):
                                cover_url = f"https://kemono.cr{src}"
                            else:
                                cover_url = src

                    results.append({
                        'title': name,
                        'url': full_url,
                        'author': service, # Using service as author field for identification
                        'cover_url': cover_url,
                        'provider': 'Kemono'
                    })

            except Exception as e:
                print(f"Kemono search error: {e}")
            finally:
                browser.close()

        return results
