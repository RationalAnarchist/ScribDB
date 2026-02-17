from playwright.sync_api import sync_playwright, expect
import time
import subprocess

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.goto("http://127.0.0.1:8000")
        print("Page loaded")

        # Dump content for debugging
        with open("verification/page_dump.html", "w") as f:
            f.write(page.content())

        # Check if we have any story
        stories = page.locator(".group") # The card container class
        count = stories.count()
        print(f"Found {count} stories")

        if count == 0:
            print("No stories found!")
            page.screenshot(path="verification/failure.png")
            return

        # Try to find the ID
        # The ID is chapter-count-{{ story.id }}
        # Let's find any element starting with chapter-count-
        counts = page.locator("[id^='chapter-count-']")
        print(f"Found {counts.count()} chapter count elements")

        if counts.count() > 0:
            first_id = counts.first.get_attribute("id")
            print(f"First ID found: {first_id}")
            grid_count = page.locator(f"#{first_id}")
            expect(grid_count).to_be_visible()
            expect(grid_count).to_contain_text("5 / 10")
        else:
            print("No chapter count elements found with ID pattern")
            page.screenshot(path="verification/failure.png")
            return

        # Take Screenshot 1: Initial Grid View
        page.screenshot(path="verification/grid_view_initial.png")
        print("Grid View Initial Screenshot Taken")

        # Switch to List View
        page.click("#btn-list")

        # Check List View
        # Construct list ID from the found story ID
        story_id = first_id.split("-")[-1]
        list_count = page.locator(f"#list-chapter-count-{story_id}")
        expect(list_count).to_be_visible()
        expect(list_count).to_contain_text("5 / 10")

        # Take Screenshot 2: Initial List View
        page.screenshot(path="verification/list_view_initial.png")
        print("List View Initial Screenshot Taken")

        # Trigger DB update
        # We need to make sure update_db updates the SAME story.
        # update_db just picks the first pending chapter. Since we only seeded one story, it should be fine.
        subprocess.run(["python3", "update_db.py"])

        # Wait for polling (5s interval + buffer)
        print("Waiting for polling update...")
        time.sleep(6)

        # Check updated text: "6 / 10" in List View (still visible)
        expect(list_count).to_contain_text("6 / 10")

        # Take Screenshot 3: Updated List View
        page.screenshot(path="verification/list_view_updated.png")
        print("List View Updated Screenshot Taken")

        # Switch back to Grid View to verify it updated too while hidden
        page.click("#btn-grid")
        expect(grid_count).to_be_visible()
        expect(grid_count).to_contain_text("6 / 10")

        # Take Screenshot 4: Updated Grid View
        page.screenshot(path="verification/grid_view_updated.png")
        print("Grid View Updated Screenshot Taken")

    except Exception as e:
        print(f"Error: {e}")
        page.screenshot(path="verification/error.png")
        raise e
    finally:
        browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
