#!/usr/bin/env python

import re

def kemono(url, output, browser=None):
    try:
        from playwright.sync_api import sync_playwright # type: ignore
    except ImportError:
        print("Playwright not installed. Cannot scrape Kemono.")
        raise ImportError("Playwright not installed")

    try:
        print(f"Scraping content from {url} using Playwright...")

        if browser:
            _scrape_page(browser, url, output)
        else:
            with sync_playwright() as p:
                browser_instance = p.chromium.launch(headless=True)
                try:
                    _scrape_page(browser_instance, url, output)
                finally:
                    browser_instance.close()

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        output.append(f"<p>Error loading content: {e}</p>")

def _scrape_page(browser, url, output):
    page = browser.new_page()
    try:
        # Go to page
        page.goto(url, timeout=90000)

        # Wait for content to load
        # Usually .post__content or .post-content
        try:
            # Wait for either class
            page.wait_for_selector('.post__content, .post-content', timeout=20000)
        except:
            print("Timeout waiting for content div. Page might be empty or restricted.")

        content_html = ""

        # Try getting the content div
        content_el = page.query_selector('.post__content')
        if not content_el:
            content_el = page.query_selector('.post-content')

        if content_el:
            content_html = content_el.inner_html()

        # If content is empty or small, look for file/attachments in DOM
        # Kemono often displays the main file as an img or video tag outside the content div,
        # or simply as part of the post layout.

        # Look for post file (often class .post__file or similar, or just img in .post__thumbnail)
        # Inspecting common structure:
        # <div class="post__thumbnail"> <a ...> <img src="..."> </a> </div>

        attachments_html = ""

        # Check for main file thumbnail/image
        thumb_el = page.query_selector('.post__thumbnail img')
        if thumb_el:
            src = thumb_el.get_attribute('src')
            if src:
                # Resolve relative URL
                if src.startswith('/'):
                    src = "https://kemono.cr" + src
                attachments_html += f'<img src="{src}" /><br/>'

        # Check for other attachments if listed as thumbnails
        # .post__attachments .post__attachment a
        atts = page.query_selector_all('.post__attachment a')
        for att in atts:
            href = att.get_attribute('href')
            # If it's an image, maybe we want to embed it?
            # Check for download attribute or just assume it's a file.
            # Usually we want the image preview if available.
            # .post__attachment-thumb
            thumb = att.query_selector('.post__attachment-thumb')
            if thumb:
                src = thumb.get_attribute('src')
                if src:
                    if src.startswith('/'):
                        src = "https://kemono.cr" + src
                    attachments_html += f'<img src="{src}" /><br/>'
            elif href and (href.endswith('.jpg') or href.endswith('.png')):
                    if href.startswith('/'):
                        href = "https://kemono.cr" + href
                    attachments_html += f'<img src="{href}" /><br/>'

        if content_html:
            output.append(content_html)

        if attachments_html:
            output.append(attachments_html)

        if not content_html and not attachments_html:
            output.append("<p>Content not found.</p>")
            print(f"Warning: No content or attachments found for {url}")

    finally:
        page.close()
