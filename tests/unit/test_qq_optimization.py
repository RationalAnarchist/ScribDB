import unittest
import sys
import os
from unittest.mock import MagicMock
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrollarr.sources.questionablequesting import QuestionableQuestingAllPostsSource

class TestQQOptimization(unittest.TestCase):
    def test_start_from_last_chapter_page(self):
        source = QuestionableQuestingAllPostsSource()
        source.requester = MagicMock()

        url = "https://forum.questionablequesting.com/threads/my-story.1234/"
        last_chapter = {
            'url': 'https://forum.questionablequesting.com/posts/200/',
            'title': 'Volume 2',
            'volume_title': 'Volume 2',
            'volume_number': 2,
            'index': 3
        }

        # HTML for Threadmarks
        html_tm = """
        <html>
            <div class="structItem--threadmark">
                <div class="structItem-title"><a href="threads/my-story.1234/post-100">Volume 1</a></div>
            </div>
            <div class="structItem--threadmark">
                <div class="structItem-title"><a href="threads/my-story.1234/post-200">Volume 2</a></div>
            </div>
        </html>
        """

        # HTML for Metadata
        html_meta = """
        <html>
             <div class="p-description"><a class="username">TestAuthor</a></div>
             <h1 class="p-title-value">My Story</h1>
        </html>
        """

        # HTML for Page 2 (where last chapter is)
        html_page_2 = """
        <html>
            <div class="p-description"><a class="username">TestAuthor</a></div>

            <!-- Post 200: TM 2 (Last Known) -->
            <article class="message--post" data-content="post-200">
                <div class="message-userDetails"><a class="username">TestAuthor</a></div>
                <div class="bbWrapper">Content 2</div>
            </article>

             <!-- Post 201: New Content -->
            <article class="message--post" data-content="post-201">
                <div class="message-userDetails"><a class="username">TestAuthor</a></div>
                <div class="bbWrapper">Content 2.2</div>
            </article>
        </html>
        """

        def side_effect(req_url, allow_redirects=True):
            if 'threadmarks' in req_url:
                m = MagicMock()
                m.text = html_tm
                return m
            elif req_url == last_chapter['url']:
                # Simulate redirect to page 2
                m = MagicMock()
                m.url = "https://forum.questionablequesting.com/threads/my-story.1234/page-2#post-200"
                return m
            elif 'page-2' in req_url:
                 m = MagicMock()
                 m.text = html_page_2
                 m.url = req_url
                 return m
            elif 'threads/my-story.1234' in req_url: # Page 1
                 # Should NOT be called for crawling if optimized
                 # But get_metadata calls it for title/author
                 m = MagicMock()
                 m.text = html_meta
                 return m
            else:
                 m = MagicMock()
                 m.text = html_meta
                 return m

        source.requester.get.side_effect = side_effect

        chapters = source.get_chapter_list(url, last_chapter=last_chapter)

        # Verify calls
        # We expect a call to threadmarks
        # We expect a call to last_chapter['url'] (HEAD/GET)
        # We expect a call to page 2

        # Verify that we extracted chapters from page 2 correctly
        self.assertEqual(len(chapters), 2)

        # Post 200 (Last known) - Should be synced
        # title should be Volume 2 (because it's a threadmark and we synced or it is identified as TM)
        self.assertEqual(chapters[0]['title'], "Volume 2")
        self.assertEqual(chapters[0]['volume_title'], "Volume 2")

        # Post 201 (New) - Should have correct part counter
        # Post 200 was TM, so part_counter=1.
        # Post 201 should be Volume 2 - Part 2.
        self.assertEqual(chapters[1]['title'], "Volume 2 - Part 2")
        self.assertEqual(chapters[1]['volume_title'], "Volume 2")

    def test_sync_part_counter(self):
        source = QuestionableQuestingAllPostsSource()
        source.requester = MagicMock()

        url = "https://forum.questionablequesting.com/threads/my-story.1234/"
        last_chapter = {
            'url': 'https://forum.questionablequesting.com/posts/205/',
            'title': 'Volume 2 - Part 5', # Implies part_counter 5
            'volume_title': 'Volume 2',
            'volume_number': 2,
            'index': 7
        }

         # HTML for Threadmarks (Only Vol 1 and 2 exist)
        html_tm = """
        <html>
            <div class="structItem--threadmark">
                <div class="structItem-title"><a href="threads/my-story.1234/post-100">Volume 1</a></div>
            </div>
            <div class="structItem--threadmark">
                <div class="structItem-title"><a href="threads/my-story.1234/post-200">Volume 2</a></div>
            </div>
        </html>
        """

        html_meta = """<html><div class="p-description"><a class="username">TestAuthor</a></div><h1 class="p-title-value">My Story</h1></html>"""

        # Page 3 containing post 205
        html_page_3 = """
        <html>
            <div class="p-description"><a class="username">TestAuthor</a></div>

            <!-- Post 204: Part 4 (Before last known) -->
            <article class="message--post" data-content="post-204">
                <div class="message-userDetails"><a class="username">TestAuthor</a></div>
                <div class="bbWrapper">Content 2.4</div>
            </article>

            <!-- Post 205: Part 5 (Last Known) -->
            <article class="message--post" data-content="post-205">
                <div class="message-userDetails"><a class="username">TestAuthor</a></div>
                <div class="bbWrapper">Content 2.5</div>
            </article>

             <!-- Post 206: New Content -->
            <article class="message--post" data-content="post-206">
                <div class="message-userDetails"><a class="username">TestAuthor</a></div>
                <div class="bbWrapper">Content 2.6</div>
            </article>
        </html>
        """

        def side_effect(req_url, allow_redirects=True):
            if 'threadmarks' in req_url:
                m = MagicMock()
                m.text = html_tm
                return m
            elif req_url == last_chapter['url']:
                m = MagicMock()
                m.url = "https://forum.questionablequesting.com/threads/my-story.1234/page-3#post-205"
                return m
            elif 'page-3' in req_url:
                 m = MagicMock()
                 m.text = html_page_3
                 m.url = req_url
                 return m
            else:
                 m = MagicMock()
                 m.text = html_meta
                 return m

        source.requester.get.side_effect = side_effect

        chapters = source.get_chapter_list(url, last_chapter=last_chapter)

        # We now skip posts before the sync point to maintain index consistency.
        # So we expect 205 (sync point) and 206 (new). 204 is skipped.
        self.assertEqual(len(chapters), 2) # 205, 206

        # Post 206 should be "Volume 2 - Part 6".
        self.assertEqual(chapters[1]['title'], "Volume 2 - Part 6")
        self.assertEqual(chapters[1]['volume_title'], "Volume 2")

if __name__ == '__main__':
    unittest.main()
