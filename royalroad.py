from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict
import json

from core_logic import BaseSource
from polite_requester import PoliteRequester

class RoyalRoadSource(BaseSource):
    BASE_URL = "https://www.royalroad.com"

    def __init__(self):
        self.requester = PoliteRequester()

    def identify(self, url: str) -> bool:
        return 'royalroad.com' in url

    def get_metadata(self, url: str) -> Dict:
        response = self.requester.get(url)
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

        # New metadata fields
        tags = []
        for tag in soup.select('.tags .fiction-tag'):
            tags.append(tag.get_text(strip=True))

        rating = None
        # Try JSON-LD first
        ld_json = soup.find('script', type='application/ld+json')
        if ld_json:
            try:
                data = json.loads(ld_json.string)
                if 'aggregateRating' in data:
                    rating = str(round(float(data['aggregateRating'].get('ratingValue', 0)), 2))
                if not tags and 'genre' in data:
                    # JSON-LD genre is a list of strings
                    tags = data['genre']
            except Exception:
                pass

        status = "Unknown"
        # Look for status label in labels
        status_labels = soup.select('.label')
        for label in status_labels:
            text = label.get_text(strip=True).upper()
            if text in ['COMPLETED', 'ONGOING', 'HIATUS', 'DROPPED', 'STUB']:
                status = text.title()
                break

        language = "English"

        return {
            'title': title,
            'author': author,
            'description': description,
            'cover_url': cover_url,
            'tags': ", ".join(tags) if tags else None,
            'rating': rating,
            'language': language,
            'publication_status': status
        }

    def get_chapter_list(self, url: str) -> List[Dict]:
        response = self.requester.get(url)
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
        response = self.requester.get(chapter_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        content_div = soup.select_one('.chapter-inner')
        if not content_div:
            content_div = soup.select_one('.content')

        if content_div:
            # Remove scripts and styles
            for tag in content_div(['script', 'style']):
                tag.decompose()

            # Remove known unwanted elements
            for tag in content_div.select('.nav-buttons, .author-note-portlet'):
                tag.decompose()

            # Remove specific text patterns
            unwanted_phrases = ['Next Chapter', 'Previous Chapter', 'Support the Author', 'Donate', 'Patreon', 'Ko-fi']

            # Find candidate elements to remove based on text
            candidates = []
            for text_node in content_div.find_all(string=True):
                if any(phrase in text_node for phrase in unwanted_phrases):
                    parent = text_node.parent
                    if parent and parent != content_div:
                        candidates.append(parent)

            # Remove unique candidates
            for element in set(candidates):
                # Check if element is still in tree
                if element.parent:
                    text = element.get_text(strip=True)
                    if element.name == 'a':
                        if any(phrase in text for phrase in unwanted_phrases):
                            element.decompose()
                    elif element.name in ['p', 'div', 'span', 'strong', 'em']:
                        classes = element.get('class', [])
                        # Handle partial match for portlet classes (e.g. author-note-portlet)
                        if classes and any('portlet' in cls for cls in classes):
                            element.decompose()
                        elif len(text) < 100:
                            # Avoid removing dialogue which usually contains quotes
                            if '"' in text or '“' in text or '”' in text:
                                continue

                            if any(phrase in text for phrase in unwanted_phrases):
                                element.decompose()

            # Return inner HTML
            return content_div.decode_contents()

        return ""

    def search(self, query: str) -> List[Dict]:
        url = f"{self.BASE_URL}/fictions/search?title={query}"
        response = self.requester.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('.fiction-list-item'):
            title_tag = item.select_one('.fiction-title a')
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            story_url = urljoin(self.BASE_URL, title_tag['href'])

            author = "Unknown"
            # Look for author link
            for a in item.select('a'):
                if a.get('href', '').startswith('/profile/'):
                    author = a.get_text(strip=True)
                    break

            cover_url = None
            img = item.select_one('img')
            if img and img.has_attr('src'):
                src = img['src']
                if src.startswith('/'):
                    src = urljoin(self.BASE_URL, src)
                cover_url = src

            results.append({
                'title': title,
                'url': story_url,
                'author': author,
                'cover_url': cover_url,
                'provider': 'Royal Road'
            })

        return results
