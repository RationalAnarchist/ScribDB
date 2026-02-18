import os
from playwright.sync_api import sync_playwright

def verify_import_page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            # Go to import page
            page.goto("http://localhost:8000/import")

            # Check title
            title = page.title()
            print(f"Page title: {title}")
            assert "Import - Scrollarr" in title

            # Check for Scan Section
            assert page.get_by_text("Scan Local Folder").is_visible()

            # Check for Upload Section
            assert page.get_by_text("Upload File").is_visible()

            # Take screenshot
            os.makedirs("verification", exist_ok=True)
            page.screenshot(path="verification/import_page.png")
            print("Screenshot saved to verification/import_page.png")

        except Exception as e:
            print(f"Verification failed: {e}")
            # Try to take screenshot anyway if possible
            try:
                os.makedirs("verification", exist_ok=True)
                page.screenshot(path="verification/error_screenshot.png")
            except:
                pass
        finally:
            browser.close()

if __name__ == "__main__":
    verify_import_page()
