from playwright.sync_api import sync_playwright, expect
import os

def verify_nav_buttons():
    # Use the absolute path to the file
    file_path = os.path.abspath("web/templates/index.html")
    file_url = f"file://{file_path}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(file_url)

        # Verify North Button
        north_btn = page.locator("button[data-dir='north']")
        expect(north_btn).to_have_attribute("aria-label", "North")
        expect(north_btn).to_have_attribute("aria-keyshortcuts", "ArrowUp")
        print("North button verified.")

        # Verify West Button
        west_btn = page.locator("button[data-dir='west']")
        expect(west_btn).to_have_attribute("aria-label", "West")
        expect(west_btn).to_have_attribute("aria-keyshortcuts", "ArrowLeft")
        print("West button verified.")

        # Verify Center Button
        center_btn = page.locator(".nav-center")
        expect(center_btn).to_have_attribute("aria-label", "Current Location")
        print("Center button verified.")

        # Verify East Button
        east_btn = page.locator("button[data-dir='east']")
        expect(east_btn).to_have_attribute("aria-label", "East")
        expect(east_btn).to_have_attribute("aria-keyshortcuts", "ArrowRight")
        print("East button verified.")

        # Verify South Button
        south_btn = page.locator("button[data-dir='south']")
        expect(south_btn).to_have_attribute("aria-label", "South")
        expect(south_btn).to_have_attribute("aria-keyshortcuts", "ArrowDown")
        print("South button verified.")

        page.screenshot(path="verification/nav_buttons.png")
        print("Screenshot saved to verification/nav_buttons.png")

        browser.close()

if __name__ == "__main__":
    verify_nav_buttons()
