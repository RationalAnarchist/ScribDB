import time
import random
import requests
from typing import Dict, Optional

class PoliteRequester:
    """
    A wrapper around requests to be polite to servers.
    Adds random delays between requests and uses realistic browser headers.
    """
    def __init__(self, delay_range: tuple = (2, 5)):
        self.delay_range = delay_range
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }

    def get(self, url: str) -> requests.Response:
        """
        Sends a GET request to the specified URL with a random delay.

        Args:
            url: The URL to fetch.

        Returns:
            requests.Response: The response object.
        """
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response
