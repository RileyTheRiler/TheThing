from playwright.sync_api import sync_playwright
import os

def verify_ux():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        cwd = os.getcwd()
        file_url = f"file://{cwd}/web/templates/index.html"

        print(f"Loading {file_url}")
        page.goto(file_url)

        # Verify Command Input has aria-label
        input_el = page.locator("#command-input")
        aria_label = input_el.get_attribute("aria-label")
        print(f"Command Input aria-label: {aria_label}")

        # Verify Nav Buttons
        north_btn = page.locator(".nav-btn[data-dir=\"north\"]")
        north_label = north_btn.get_attribute("aria-label")
        print(f"North Button aria-label: {north_label}")

        # Verify Modal Close
        modal_close = page.locator(".modal-close").first
        close_label = modal_close.get_attribute("aria-label")
        print(f"Modal Close aria-label: {close_label}")

        page.screenshot(path="verification/ux_verification.png")
        print("Screenshot saved to verification/ux_verification.png")

if __name__ == "__main__":
    verify_ux()
