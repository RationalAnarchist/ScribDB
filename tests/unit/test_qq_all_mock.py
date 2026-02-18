import unittest
import sys
import os
from unittest.mock import MagicMock
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrollarr.sources.questionablequesting import QuestionableQuestingAllPostsSource
import re

class TestQQAllPosts(unittest.TestCase):
    def test_chapter_list_parsing(self):
        source = QuestionableQuestingAllPostsSource()
        source.requester = MagicMock()

        url = "https://forum.questionablequesting.com/threads/my-story.1234/"

        # HTML for Metadata (Page 1 of thread usually)
        html_meta = """
        <html>
            <div class="p-description"><a class="username">TestAuthor</a></div>
            <h1 class="p-title-value">My Story</h1>
        </html>
        """

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

        # HTML for Thread Page 1
        html_thread = """
        <html>
             <div class="p-description"><a class="username">TestAuthor</a></div>

            <!-- Post 100: TM 1 -->
            <article class="message--post" data-content="post-100">
                <div class="message-userDetails"><a class="username">TestAuthor</a></div>
                <div class="bbWrapper">Content 1</div>
            </article>

            <!-- Post 101: Content 1.2 -->
            <article class="message--post" data-content="post-101">
                <div class="message-userDetails"><a class="username">TestAuthor</a></div>
                <div class="bbWrapper">Content 1.2</div>
            </article>

            <!-- Post 102: Random User -->
            <article class="message--post" data-content="post-102">
                <div class="message-userDetails"><a class="username">RandomUser</a></div>
                <div class="bbWrapper">Spam</div>
            </article>

            <!-- Post 200: TM 2 -->
            <article class="message--post" data-content="post-200">
                <div class="message-userDetails"><a class="username">TestAuthor</a></div>
                <div class="bbWrapper">Content 2</div>
            </article>

             <!-- Post 201: Content 2.2 -->
            <article class="message--post" data-content="post-201">
                <div class="message-userDetails"><a class="username">TestAuthor</a></div>
                <div class="bbWrapper">Content 2.2</div>
            </article>
        </html>
        """

        def side_effect(req_url):
            if 'threadmarks' in req_url:
                m = MagicMock()
                m.text = html_tm
                return m
            elif 'threads/my-story.1234' in req_url:
                 m = MagicMock()
                 m.text = html_thread
                 return m
            else:
                 m = MagicMock()
                 m.text = html_meta
                 return m

        source.requester.get.side_effect = side_effect

        chapters = source.get_chapter_list(url)

        # Verify
        self.assertEqual(len(chapters), 4) # 100, 101, 200, 201

        # Chap 1 (Post 100) -> TM 1
        self.assertEqual(chapters[0]['title'], "Volume 1")
        self.assertEqual(chapters[0]['volume_title'], "Volume 1")
        self.assertEqual(chapters[0]['volume_number'], 1)

        # Chap 2 (Post 101) -> Part 2
        self.assertEqual(chapters[1]['title'], "Volume 1 - Part 2")
        self.assertEqual(chapters[1]['volume_title'], "Volume 1")

        # Chap 3 (Post 200) -> TM 2
        self.assertEqual(chapters[2]['title'], "Volume 2")
        self.assertEqual(chapters[2]['volume_title'], "Volume 2")
        self.assertEqual(chapters[2]['volume_number'], 2)

        # Chap 4 (Post 201) -> Part 2
        self.assertEqual(chapters[3]['title'], "Volume 2 - Part 2")
        self.assertEqual(chapters[3]['volume_title'], "Volume 2")

if __name__ == '__main__':
    unittest.main()
