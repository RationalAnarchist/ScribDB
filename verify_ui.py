from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # 1. Visit Settings
        print("Visiting settings...")
        try:
            page.goto("http://localhost:8000/settings", timeout=10000)
            page.wait_for_selector("text=Library Organization")
            # Scroll to show new fields
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.screenshot(path="verification_settings.png")
            print("Settings screenshot taken.")
        except Exception as e:
            print(f"Error visiting settings: {e}")

        # 2. Visit Dashboard and check modal
        print("Visiting dashboard...")
        try:
            page.goto("http://localhost:8000/", timeout=10000)
            # Wait for modal
            try:
                page.wait_for_selector("#migration-modal:not(.hidden)", timeout=5000)
                print("Modal appeared.")
                page.screenshot(path="verification_modal.png")
            except Exception:
                print("Modal did not appear within timeout.")
                page.screenshot(path="verification_dashboard.png")
        except Exception as e:
            print(f"Error visiting dashboard: {e}")

        browser.close()

if __name__ == "__main__":
    run()
