import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict

from core_logic import BaseSource

class RoyalRoadSource(BaseSource):
    BASE_URL = "https://www.royalroad.com"

    def identify(self, url: str) -> bool:
        return 'royalroad.com' in url

    def get_metadata(self, url: str) -> Dict:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

        author_tag = soup.find('h4')
        author = "Unknown Author"
        if author_tag:
            author_link = author_tag.find('a')
            if author_link:
                author = author_link.get_text(strip=True)
            else:
                text = author_tag.get_text(strip=True)
                if text.lower().startswith('by '):
                    author = text[3:].strip()
                else:
                    author = text

        description_div = soup.select_one('.description > .hidden-content')
        if not description_div:
            description_div = soup.select_one('.description')

        description = description_div.get_text("\n", strip=True) if description_div else "No description available."

        cover_img = soup.select_one('img.thumbnail')
        cover_url = None
        if cover_img and cover_img.has_attr('src'):
            cover_url = urljoin(self.BASE_URL, cover_img['src'])

        return {
            'title': title,
            'author': author,
            'description': description,
            'cover_url': cover_url
        }

    def get_chapter_list(self, url: str) -> List[Dict]:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        chapters = []
        table = soup.find('table', id='chapters')
        if table:
            for row in table.find_all('tr', class_='chapter-row'):
                link = row.find('a', href=True)
                if link:
                    title = link.get_text(strip=True)
                    chapter_url = urljoin(self.BASE_URL, link['href'])
                    chapters.append({
                        'title': title,
                        'url': chapter_url
                    })
        return chapters

    def get_chapter_content(self, chapter_url: str) -> str:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(chapter_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        content_div = soup.select_one('.chapter-inner')
        if not content_div:
            content_div = soup.select_one('.content')

        if content_div:
            # Remove scripts and styles
            for tag in content_div(['script', 'style']):
                tag.decompose()

            # Return inner HTML
            # We can use decode_contents() to get inner HTML string
            return content_div.decode_contents()

        return ""
