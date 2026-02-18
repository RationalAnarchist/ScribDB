import time
import random
import requests
from typing import Dict, Optional
from .config import config_manager

class PoliteRequester:
    """
    A wrapper around requests to be polite to servers.
    Adds random delays between requests and uses realistic browser headers.
    """
    def __init__(self, delay_range: tuple = None):
        if delay_range is None:
            min_delay = config_manager.get('min_delay', 2.0)
            max_delay = config_manager.get('max_delay', 5.0)
            self.delay_range = (min_delay, max_delay)
        else:
            self.delay_range = delay_range

        self.headers = {
            'User-Agent': config_manager.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }
        self.cookies = {}

    def set_cookies(self, cookies: Dict):
        """
        Sets cookies for subsequent requests.
        """
        self.cookies = cookies

    def get(self, url: str, timeout: int = 30) -> requests.Response:
        """
        Sends a GET request to the specified URL with a random delay.

        Args:
            url: The URL to fetch.
            timeout: Request timeout in seconds.

        Returns:
            requests.Response: The response object.
        """
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

        response = requests.get(url, headers=self.headers, cookies=self.cookies, timeout=timeout)
        response.raise_for_status()
        return response
