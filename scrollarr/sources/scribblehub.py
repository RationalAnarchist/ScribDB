import re
import time
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from ..core_logic import BaseSource

class ScribbleHubSource(BaseSource):
    key = "scribblehub"
    name = "Scribble Hub"
    is_enabled_by_default = True

    def identify(self, url: str) -> bool:
        return 'scribblehub.com' in url

    def _get_playwright(self):
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright()
        except ImportError:
            raise ImportError("Playwright is not installed. Please install it to use Scribble Hub source.")

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

    def _scrape_page(self, url: str, wait_selector: str = None) -> str:
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

            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            try:
                page.set_default_timeout(60000)
                page.goto(url, wait_until="domcontentloaded")

                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=10000)
                    except:
                        # Log warning but continue if possible
                        print(f"Warning: Selector {wait_selector} not found on {url}")

                # Wait a bit for dynamic content
                time.sleep(2)

                content = page.content()
                return content
            finally:
                browser.close()

    def get_metadata(self, url: str) -> Dict:
        html = self._scrape_page(url, wait_selector='.fic_title')
        soup = BeautifulSoup(html, 'html.parser')

        title_tag = soup.select_one('.fic_title')
        title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

        author_tag = soup.select_one('.auth_name_fic')
        author = author_tag.get_text(strip=True) if author_tag else "Unknown Author"

        desc_tag = soup.select_one('.fic_description') or soup.select_one('.wi_fic_desc')
        description = desc_tag.get_text("\n", strip=True) if desc_tag else "No description available."

        cover_tag = soup.select_one('.fic_image img')
        cover_url = cover_tag['src'] if cover_tag else None

        tags = [t.get_text(strip=True) for t in soup.select('.wi_fic_showtags a.stag')]

        # Status - try to find it in metadata table
        # Structure is usually table or list.
        # Alternatively, .widget_fic_similar often contains status but it's not reliable.
        # Let's check for 'Status' label in .fic_stats or similar if possible.
        # For now, default to Unknown or parse if found.
        status = "Unknown"
        # Often found in <span class="rnd_stats">...</span>

        return {
            'title': title,
            'author': author,
            'description': description,
            'cover_url': cover_url,
            'tags': ", ".join(tags) if tags else None,
            'rating': None, # Rating logic can be added later if needed
            'language': 'English',
            'publication_status': status
        }

    def get_chapter_list(self, url: str, **kwargs) -> List[Dict]:
        chapters = []

        with self._get_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    self._ensure_browser_installed()
                    browser = p.chromium.launch(headless=True)
                else:
                    raise e

            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

            try:
                current_url = url
                while True:
                    # Navigate to current page
                    page.goto(current_url, wait_until="domcontentloaded")

                    try:
                        page.wait_for_selector('li.toc_w', timeout=10000)
                    except:
                        break # No chapters found on this page?

                    # Parse current page chapters
                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')

                    toc_items = soup.select('li.toc_w')
                    if not toc_items:
                        break

                    for item in toc_items:
                        link = item.select_one('a.toc_a')
                        if not link:
                            continue

                        title = link.get_text(strip=True)
                        chapter_url = link['href']

                        published_date = None
                        date_span = item.select_one('span.fic_date_pub')
                        if date_span:
                            date_text = date_span.get_text(strip=True)
                            title_attr = date_span.get('title', '')

                            # Parse date
                            # Formats: "X mins ago", "X hours ago", "Jan 1, 2023", "Yesterday"
                            raw_date = title_attr if title_attr else date_text

                            try:
                                if 'ago' in raw_date:
                                    # Handle relative time roughly or ignore
                                    # Usually "21 mins ago" -> assume today
                                    published_date = datetime.now()
                                    if 'min' in raw_date:
                                        mins = int(re.search(r'\d+', raw_date).group())
                                        published_date -= timedelta(minutes=mins)
                                    elif 'hour' in raw_date:
                                        hours = int(re.search(r'\d+', raw_date).group())
                                        published_date -= timedelta(hours=hours)
                                    elif 'day' in raw_date:
                                        days = int(re.search(r'\d+', raw_date).group())
                                        published_date -= timedelta(days=days)
                                else:
                                    # Try parsing specific format found in title attribute: "Feb 13, 2026 07:37 PM"
                                    # Or "Feb 5, 2026"
                                    published_date = datetime.strptime(raw_date, "%b %d, %Y %I:%M %p")
                            except:
                                try:
                                     published_date = datetime.strptime(raw_date, "%b %d, %Y")
                                except:
                                    pass

                        chapters.append({
                            'title': title,
                            'url': chapter_url,
                            'published_date': published_date
                        })

                    # Check for Next Page
                    next_link = soup.select_one('a.page-link.next') or soup.select_one('span.next a') # Fallback selector

                    if next_link and next_link.has_attr('href'):
                        href = next_link['href']
                        if 'toc=' in href:
                             # Scribble Hub pagination links are relative usually? No, inspected HTML showed `?toc=2#content1`
                             # Need to combine with base URL if relative
                             if href.startswith('?'):
                                 # Construct full URL based on original series URL (without query params)
                                 base = url.split('?')[0]
                                 current_url = f"{base}{href}"
                             else:
                                 current_url = href

                             # Safety check to avoid infinite loops if next points to same page
                             if current_url == page.url:
                                 break
                        else:
                            break
                    else:
                        break

            finally:
                browser.close()

        # Sort chapters by date if possible, but usually order on page is reverse chronological (newest first).
        # We usually want oldest first (chapter 1).
        # The inspected HTML showed Chapter 311 first, then 18 (weird), then 310.
        # Wait, the inspected HTML showed:
        # Chapter 311 (21 mins ago)
        # Chapter 18 (45 mins ago) -> Wait, maybe it's chapter 18 of Volume X? Or weird numbering.
        # Usually Scribble Hub lists newest first.
        # We should reverse the list to get Chapter 1 first.
        chapters.reverse()

        return chapters

    def get_chapter_content(self, chapter_url: str) -> str:
        html = self._scrape_page(chapter_url, wait_selector='#chp_raw')
        soup = BeautifulSoup(html, 'html.parser')

        content_div = soup.select_one('#chp_raw') or soup.select_one('#chp_contents')

        if content_div:
            # Cleanup
            # Remove scripts
            for s in content_div(['script', 'style']):
                s.decompose()

            # Remove ads or unwanted elements if known
            # e.g. .ad_content, .patreon-button

            return content_div.decode_contents()

        return ""

    def search(self, query: str) -> List[Dict]:
        search_url = f"https://www.scribblehub.com/?s={query}&post_type=fictionposts"
        html = self._scrape_page(search_url, wait_selector='.search_main_box')
        soup = BeautifulSoup(html, 'html.parser')

        results = []
        for item in soup.select('.search_main_box'):
            title_tag = item.select_one('.search_title a')
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            url = title_tag['href']

            cover_tag = item.select_one('.search_img img')
            cover_url = cover_tag['src'] if cover_tag else None

            # Author
            # Found in: <span title="Author">... <a href="...">AuthorName</a></span>
            author = "Unknown"
            author_span = item.select_one('span[title="Author"] a')
            if author_span:
                author = author_span.get_text(strip=True)

            results.append({
                'title': title,
                'url': url,
                'author': author,
                'cover_url': cover_url,
                'provider': 'Scribble Hub'
            })

        return results
