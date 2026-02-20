import re
import time
import subprocess
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from ..core_logic import BaseSource

class WattpadSource(BaseSource):
    key = "wattpad"
    name = "Wattpad"
    is_enabled_by_default = True

    def identify(self, url: str) -> bool:
        return 'wattpad.com' in url

    def _get_playwright(self):
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright()
        except ImportError:
            raise ImportError("Playwright is not installed. Please install it to use Wattpad source.")

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

    def get_metadata(self, url: str) -> Dict:
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
                page.goto(url, wait_until="domcontentloaded")
                # Wait for title
                try:
                    page.wait_for_selector('h1', timeout=10000)
                except:
                    pass

                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

                # Title
                title = "Unknown Title"
                h1 = soup.find('h1')
                if h1:
                    title = h1.get_text(strip=True)

                # Author
                author = "Unknown Author"
                author_link = soup.select_one('a[href^="/user/"]')
                if author_link:
                    author = author_link.get_text(strip=True)

                # Description
                description = "No description available."
                og_desc = soup.find('meta', property='og:description')
                if og_desc:
                    description = og_desc.get('content', '')
                else:
                    desc_div = soup.select_one('.description')
                    if desc_div:
                        description = desc_div.get_text(strip=True)

                # Cover
                cover_url = None
                og_image = soup.find('meta', property='og:image')
                if og_image:
                    cover_url = og_image.get('content')

                # Status
                publication_status = "Ongoing"
                if "Complete" in soup.get_text():
                    publication_status = "Completed"

                # Tags
                tags = []
                for tag in soup.select('.tag-items li a'):
                    tags.append(tag.get_text(strip=True))

                return {
                    'title': title,
                    'author': author,
                    'description': description,
                    'cover_url': cover_url,
                    'tags': ", ".join(tags) if tags else None,
                    'rating': None,
                    'language': "English",
                    'publication_status': publication_status
                }
            finally:
                browser.close()

    def get_chapter_list(self, url: str, **kwargs) -> List[Dict]:
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
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                hrefs = page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => ({href: a.getAttribute('href'), text: a.innerText}))")

                chapters = []
                seen_urls = set()

                # Regex for Wattpad chapter links: /12345678-chapter-title
                regex = re.compile(r'^/?(\d+)-.+$')

                for link in hrefs:
                    href = link['href']
                    text = link['text']

                    if not href:
                        continue

                    # Filter out non-chapter links
                    if '/story/' in href or '/user/' in href or '/list/' in href or '/login' in href or 'wattpad.com' in href:
                         # Check if it's a full URL that matches the chapter pattern
                         match = re.search(r'wattpad\.com/(\d+)-', href)
                         if not match:
                             continue
                    elif not regex.match(href):
                        continue

                    # Normalize URL
                    full_url = href
                    if not href.startswith('http'):
                        if not href.startswith('/'):
                            href = '/' + href
                        full_url = f"https://www.wattpad.com{href}"

                    if full_url not in seen_urls:
                        chapters.append({
                            'title': text.strip() or "Untitled Chapter",
                            'url': full_url
                        })
                        seen_urls.add(full_url)

                return chapters
            finally:
                browser.close()

    def get_chapter_content(self, chapter_url: str) -> str:
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
            full_content = []
            current_url = chapter_url

            try:
                while True:
                    print(f"Scraping chapter page: {current_url}")
                    page.goto(current_url, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)

                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Content extraction
                    # Try <pre> first
                    pre = soup.find('pre')
                    if pre:
                        full_content.append(pre.decode_contents())
                    else:
                        # Try .story-text
                        container = soup.select_one('.story-text')
                        if container:
                            full_content.append(container.decode_contents())
                        else:
                            # Try paragraphs with data-p-id
                            ps = soup.select('p[data-p-id]')
                            if ps:
                                for p_tag in ps:
                                    full_content.append(str(p_tag))

                    # Pagination check
                    next_href = page.evaluate("""() => {
                        const anchors = Array.from(document.querySelectorAll('a'));
                        const next = anchors.find(a => (a.innerText.includes('Next Page') || a.classList.contains('on-navigate-next')) && !a.innerText.includes('Next Part'));
                        return next ? next.getAttribute('href') : null;
                    }""")

                    if next_href:
                        if next_href.startswith('/'):
                            next_url = f"https://www.wattpad.com{next_href}"
                        else:
                            next_url = next_href # Handle full URL or relative without / (unlikely)

                        if next_url != current_url:
                             current_url = next_url
                             continue

                    break # No next page found

                return "".join(full_content) if full_content else "<p>No content found.</p>"

            finally:
                browser.close()

    def search(self, query: str) -> List[Dict]:
        search_url = f"https://www.wattpad.com/search/{query}"
        results = []

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
                page.goto(search_url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

                # Wattpad search results structure (from observation)
                # .story-card-data inside a .story-card link
                cards = soup.select('.story-card-data')

                for card in cards:
                    try:
                        title_div = card.select_one('.title')
                        title = title_div.get_text(strip=True) if title_div else "Unknown Title"

                        # Find parent anchor
                        # BS4 find_parent matches strictly
                        # card is <div class="story-card-data" ...>
                        # parent is <a class="story-card" href="...">
                        parent_a = card.find_parent('a', class_='story-card')
                        if not parent_a:
                            # Try finding sibling or wrapper if structure differs
                            # But based on dump, it is nested.
                            continue

                        story_url = f"https://www.wattpad.com{parent_a['href']}"

                        cover_url = None
                        img = card.select_one('.cover img')
                        if img:
                            cover_url = img.get('src')

                        author = "Unknown Author"
                        user_div = card.select_one('.username')
                        if user_div:
                            author = user_div.get_text(strip=True)
                        else:
                            # Try parsing from aria-label or other attributes if needed
                            pass

                        results.append({
                            'title': title,
                            'url': story_url,
                            'author': author,
                            'cover_url': cover_url,
                            'provider': 'Wattpad'
                        })
                    except Exception as e:
                        print(f"Error parsing Wattpad search card: {e}")
                        continue

            finally:
                browser.close()

        return results
