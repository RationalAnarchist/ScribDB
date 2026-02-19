import re
from .questionablequesting import QuestionableQuestingSource

class SpaceBattlesSource(QuestionableQuestingSource):
    BASE_URL = "https://forums.spacebattles.com"

    def identify(self, url: str) -> bool:
        return 'spacebattles.com/threads/' in url

    def _normalize_url(self, url: str) -> str:
        """
        Normalizes the URL to the base thread URL.
        Handles RSS feeds (threadmarks.rss) and page numbers.
        """
        # Regex to find the base thread URL: threads/slug.id/
        # Matches: .../threads/story-name.1234/ and .../threads/story-name.1234
        match = re.search(r'(https?://forums\.spacebattles\.com/threads/[^/]+\.\d+)', url)
        if match:
            return match.group(1) + '/'
        return url
