from abc import ABC, abstractmethod
from typing import List, Dict, Optional

# The "Contract" for any new website (Royal Road, AO3, etc.)
class BaseSource(ABC):
    @abstractmethod
    def identify(self, url: str) -> bool:
        """Returns True if this provider handles the given URL."""
        pass

    @abstractmethod
    def get_metadata(self, url: str) -> Dict:
        """Returns title, author, description, and cover_url."""
        pass

    @abstractmethod
    def get_chapter_list(self, url: str) -> List[Dict]:
        """Returns a list of chapter objects: {id, title, url}."""
        pass

    @abstractmethod
    def get_chapter_content(self, chapter_url: str) -> str:
        """Returns the raw HTML/Text content of a single chapter."""
        pass

    @abstractmethod
    def search(self, query: str) -> List[Dict]:
        """
        Searches for stories matching the query.
        Returns a list of dicts: {title, url, author, description, cover_url}
        """
        pass

    @property
    @abstractmethod
    def key(self) -> str:
        """Returns a unique key for this provider (e.g. 'royalroad', 'ao3')."""
        pass

# The "Dispatcher" that picks the right source
class SourceManager:
    def __init__(self):
        self.providers: List[BaseSource] = []

    def register_provider(self, provider: BaseSource):
        self.providers.append(provider)

    def clear_providers(self):
        self.providers = []

    def get_provider_for_url(self, url: str) -> Optional[BaseSource]:
        for provider in self.providers:
            if provider.identify(url):
                return provider
        return None

    def get_provider_by_key(self, key: str) -> Optional[BaseSource]:
        for provider in self.providers:
            if provider.key == key:
                return provider
        return None
