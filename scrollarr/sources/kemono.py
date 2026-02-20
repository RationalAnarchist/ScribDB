import re
import time
import subprocess
import os
import tempfile
import ebooklib
from ebooklib import epub
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from ..core_logic import BaseSource

class KemonoSource(BaseSource):
    BASE_URLS = ["https://kemono.cr", "https://kemono.su", "https://kemono.party"]
    key = "kemono"
    name = "Kemono"
    is_enabled_by_default = False

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

    def _get_api_data(self, page, endpoint: str):
        """Fetches data from the internal API using the browser context."""
        # Using evaluate to bypass DDG/Cloudflare/Headers issues
        # We assume the page is already on the domain
        result = page.evaluate(f"""
            async () => {{
                try {{
                    const response = await fetch('{endpoint}', {{
                        headers: {{ 'Accept': 'text/css' }}
                    }});
                    if (!response.ok) {{
                        return {{ error: 'Response not ok', status: response.status }};
                    }}
                    const data = await response.json();
                    return {{ success: true, data: data }};
                }} catch (e) {{
                    return {{ error: e.toString() }};
                }}
            }}
        """)

        if result and result.get('success'):
            return result.get('data')

        print(f"API Fetch failed for {endpoint}: {result}")
        # Debug: Print page title to see if we are blocked
        try:
            print(f"Current Page Title: {page.title()}")
        except:
            pass
        return None

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
                page.set_default_timeout(60000)
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                content = page.content()
                return content
            finally:
                browser.close()

    def get_metadata(self, url: str) -> Dict:
        # Use existing scraping logic for metadata as it works well for headers/avatars
        # Or switch to API /api/v1/{service}/user/{id}/profile

        # Let's try API first, fall back to scraping
        match = re.search(r'kemono\.(?:cr|su|party)/([^/]+)/user/([^/]+)', url)
        if match:
            service, user_id = match.groups()

            with self._get_playwright() as p:
                try:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    # Go to base URL to set context
                    page.goto(f"https://kemono.cr/{service}/user/{user_id}", wait_until="domcontentloaded")

                    profile = self._get_api_data(page, f"/api/v1/{service}/user/{user_id}/profile")
                    if profile:
                        return {
                            'title': profile.get('name', 'Unknown Title'),
                            'author': profile.get('name', 'Unknown Author'),
                            'description': f"Posts from {service}",
                            'cover_url': f"https://img.kemono.cr/icons/{service}/{user_id}",
                            'tags': None,
                            'rating': None,
                            'language': 'English',
                            'publication_status': 'Ongoing'
                        }
                except Exception as e:
                    print(f"API Metadata fetch failed: {e}")
                finally:
                    try:
                        browser.close()
                    except:
                        pass

        # Fallback to scraping
        html = self._scrape_page(url)
        soup = BeautifulSoup(html, 'html.parser')

        title_tag = soup.select_one('h1.user-header__name span')
        title = "Unknown Title"

        if title_tag and title_tag.get_text(strip=True):
            title = title_tag.get_text(strip=True)
        else:
            og_title_tag = soup.select_one('meta[property="og:title"]')
            if og_title_tag:
                og_title = og_title_tag.get('content', '')
                match = re.search(r'Posts of "(.+?)" from "(.+?)"', og_title)
                if match:
                    title = match.group(1)
                else:
                    title = og_title

        author = title
        cover_url = None
        avatar_img = soup.select_one('.user-header__avatar img')
        if avatar_img:
            src = avatar_img.get('src')
            if src:
                if src.startswith('//'):
                    cover_url = f"https:{src}"
                elif src.startswith('/'):
                    cover_url = f"https://kemono.cr{src}"
                else:
                    cover_url = src

        return {
            'title': title,
            'author': author,
            'description': "No description available.",
            'cover_url': cover_url,
            'tags': None,
            'rating': None,
            'language': 'English',
            'publication_status': 'Ongoing'
        }

    def get_chapter_list(self, url: str, **kwargs) -> List[Dict]:
        chapters = []

        match = re.search(r'kemono\.(?:cr|su|party)/([^/]+)/user/([^/]+)', url)
        if not match:
            print("Could not parse service/user from URL")
            return []

        service, user_id = match.groups()
        base_domain = "https://kemono.cr" # Force .cr for API consistency

        with self._get_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    self._ensure_browser_installed()
                    browser = p.chromium.launch(headless=True)
                else:
                    raise e

            # context = browser.new_context() # Simplify to browser.new_page() for consistency with working debug script
            page = browser.new_page()

            try:
                # 1. Navigate to base page to establish session/cookies
                # Use default wait_until (load)
                page.goto(f"{base_domain}/{service}/user/{user_id}", timeout=60000)
                # Wait for potential challenges (Cloudflare/DDG) to clear
                page.wait_for_timeout(5000)

                # 2. Build Tag Map
                # Fetch all tags
                print("Fetching tags...")
                tags_data = self._get_api_data(page, f"/api/v1/{service}/user/{user_id}/tags")
                post_tags_map = {} # post_id -> list of tags

                if tags_data:
                    # Optimize: Fetch post IDs for tags in parallel batches
                    # We use page.evaluate to run Promise.all
                    tag_names = [t['tag'] for t in tags_data]
                    print(f"Found {len(tag_names)} tags. Building tag map...")

                    # Process in chunks to avoid browser timeouts
                    chunk_size = 5
                    for i in range(0, len(tag_names), chunk_size):
                        chunk = tag_names[i:i+chunk_size]

                        # JS code to fetch multiple tag endpoints
                        js_code = """
                            async (tags) => {
                                const results = {};
                                await Promise.all(tags.map(async (tag) => {
                                    try {
                                        // Encode tag for URL
                                        const encodedTag = encodeURIComponent(tag);
                                        const res = await fetch(`/api/v1/%s/user/%s/posts?tag=${encodedTag}`, {
                                            headers: { 'Accept': 'text/css' }
                                        });
                                        if (res.ok) {
                                            const posts = await res.json();
                                            results[tag] = posts.map(p => p.id);
                                        }
                                    } catch (e) {
                                        console.error(e);
                                    }
                                }));
                                return results;
                            }
                        """ % (service, user_id)

                        chunk_results = page.evaluate(js_code, chunk)

                        # Populate map
                        for tag, post_ids in chunk_results.items():
                            for pid in post_ids:
                                if pid not in post_tags_map:
                                    post_tags_map[pid] = []
                                post_tags_map[pid].append(tag)

                        time.sleep(0.5) # Be polite

                # 3. Fetch Main Posts
                offset = 0
                has_more = True

                while has_more:
                    print(f"Fetching posts offset {offset}...")
                    posts = self._get_api_data(page, f"/api/v1/{service}/user/{user_id}/posts?o={offset}")

                    if not posts:
                        has_more = False
                        break

                    for post in posts:
                        post_id = post.get('id')
                        title = post.get('title', 'Untitled')
                        published_str = post.get('published')

                        published_date = None
                        if published_str:
                            try:
                                # Format: 2025-11-14T21:06:50
                                published_date = datetime.strptime(published_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
                            except:
                                pass

                        full_url = f"{base_domain}/{service}/user/{user_id}/post/{post_id}"

                        # Lookup tags
                        tags = post_tags_map.get(post_id, [])

                        chapters.append({
                            'title': title,
                            'url': full_url,
                            'published_date': published_date,
                            'tags': tags,
                            'index': None # Will be set by manager if needed, or we can use offset? No, manager handles it.
                        })

                    offset += 50
                    if len(posts) < 50:
                        has_more = False

                    time.sleep(1)

            finally:
                browser.close()

        # Sort by published_date ASCENDING (oldest first)
        chapters.sort(key=lambda x: x['published_date'] or datetime.min)

        return chapters

    def _extract_epub_content(self, path):
        """Extracts HTML content from an EPUB file."""
        try:
            book = epub.read_epub(path, options={'ignore_ncx': True})
            html_parts = []
            for item_id, _ in book.spine:
                item = book.get_item_with_id(item_id)
                if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                    content = item.get_content()
                    soup = BeautifulSoup(content, 'html.parser')
                    body = soup.body
                    if body:
                        html_parts.append(body.decode_contents())
                    else:
                        html_parts.append(soup.decode_contents())
            return "".join(html_parts)
        except Exception as e:
            print(f"Error extracting EPUB: {e}")
            return ""

    def get_chapter_content(self, chapter_url: str) -> str:
        output = []
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
                    pass

                content_html = ""
                content_el = page.query_selector('.post__content')
                if not content_el:
                    content_el = page.query_selector('.post-content')

                if content_el:
                    content_html = content_el.inner_html()

                attachments_html = ""
                epub_content = ""

                thumb_el = page.query_selector('.post__thumbnail img')
                if thumb_el:
                    src = thumb_el.get_attribute('src')
                    if src:
                        if src.startswith('/'):
                            src = f"https://kemono.cr{src}"
                        attachments_html += f'<img src="{src}" /><br/>'

                atts = page.query_selector_all('.post__attachment a')
                for att in atts:
                    href = att.get_attribute('href')
                    thumb = att.query_selector('.post__attachment-thumb')

                    if thumb:
                        src = thumb.get_attribute('src')
                        if src:
                            if src.startswith('/'):
                                src = f"https://kemono.cr{src}"
                            attachments_html += f'<img src="{src}" /><br/>'
                    elif href:
                        if href.endswith('.jpg') or href.endswith('.png') or href.endswith('.jpeg'):
                            if href.startswith('/'):
                                href = f"https://kemono.cr{href}"
                            attachments_html += f'<img src="{href}" /><br/>'
                        elif href.endswith('.epub'):
                            try:
                                with page.expect_download() as download_info:
                                    att.click()
                                download = download_info.value

                                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".epub")
                                os.close(tmp_fd)

                                download.save_as(tmp_path)

                                extracted = self._extract_epub_content(tmp_path)
                                if extracted:
                                    epub_content = extracted

                                os.remove(tmp_path)
                            except Exception as e:
                                print(f"Failed to download/extract EPUB: {e}")

                final_html = content_html

                if epub_content:
                    post_text = BeautifulSoup(content_html, 'html.parser').get_text(strip=True)
                    epub_text = BeautifulSoup(epub_content, 'html.parser').get_text(strip=True)

                    if len(post_text) < 100:
                        final_html = epub_content
                    elif post_text in epub_text:
                        final_html = epub_content
                    else:
                        final_html = f"{content_html}<hr/>{epub_content}"

                if final_html:
                    output.append(final_html)

                if attachments_html:
                    output.append(attachments_html)

                if not output:
                    return "<p>Content not found.</p>"

                return "".join(output)

            finally:
                browser.close()

    def search(self, query: str) -> List[Dict]:
        results = []
        search_url = f"https://kemono.cr/artists?q={query}"

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
                page.goto(search_url, wait_until="domcontentloaded")

                try:
                    page.wait_for_selector('.card-list__items', timeout=10000)
                except:
                    pass

                page.wait_for_timeout(2000)

                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

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

                    cover_url = None
                    header_div = item.select_one('.user-card__header')
                    if header_div and header_div.has_attr('style'):
                        style = header_div['style']
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
                        'author': service,
                        'cover_url': cover_url,
                        'provider': 'Kemono'
                    })

            except Exception as e:
                print(f"Kemono search error: {e}")
            finally:
                browser.close()

        return results
