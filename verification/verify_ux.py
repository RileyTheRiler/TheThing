from playwright.sync_api import sync_playwright, expect
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the app
        try:
            page.goto("http://localhost:5000")
            # Wait for content to load
            page.wait_for_selector("#start-screen")

            # Click Begin Simulation
            page.get_by_role("button", name="[ BEGIN SIMULATION ]").click()

            # Click Normal Difficulty
            page.get_by_role("button", name="[ NORMAL ]").click()

            # Wait for game screen
            page.wait_for_selector("#game-screen")

            # Check for our accessibility improvements

            # 1. Navigation Buttons
            north_btn = page.locator("button[data-dir='north']")
            expect(north_btn).to_have_attribute("aria-label", "Go North")

            # Check the span inside is hidden
            north_span = north_btn.locator("span")
            expect(north_span).to_have_attribute("aria-hidden", "true")

            # 2. Command Input Label
            # Label should exist and point to input
            label = page.locator("label[for='command-input']")
            expect(label).to_have_class("sr-only")
            expect(label).to_have_text("Enter command")

            # 3. Take screenshot
            page.screenshot(path="verification/ux_verification.png")
            print("Verification successful! Screenshot saved.")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification/error.png")

        finally:
            browser.close()

if __name__ == "__main__":
    run()
