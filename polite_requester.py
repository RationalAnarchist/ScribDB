import time
import random
import requests

class PoliteRequester:
    def __init__(self, delay_range=(2, 5)):
        self.delay_range = delay_range
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }

    def get(self, url):
        # Add a random delay to mimic human behavior
        time.sleep(random.uniform(*self.delay_range))
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.text
