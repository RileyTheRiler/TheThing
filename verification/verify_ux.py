from playwright.sync_api import sync_playwright

def verify_accessibility():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Load the file directly. Note: Playwright can load local files with file://
        # We need the absolute path.
        import os
        cwd = os.getcwd()
        file_url = f"file://{cwd}/web/templates/index.html"

        print(f"Navigating to {file_url}")
        page.goto(file_url)

        # Check for aria-labels
        # 1. Command Input
        input_el = page.locator("#command-input")
        aria_label = input_el.get_attribute("aria-label")
        print(f"Command Input aria-label: {aria_label}")
        assert aria_label == "Enter command", "Command input missing correct aria-label"

        # 2. Command Search
        search_el = page.locator("#command-search")
        aria_label = search_el.get_attribute("aria-label")
        print(f"Search Input aria-label: {aria_label}")
        assert aria_label == "Search commands", "Search input missing correct aria-label"

        # 3. Nav Buttons
        north_btn = page.locator("button[data-dir='north']")
        aria_label = north_btn.get_attribute("aria-label")
        print(f"North Button aria-label: {aria_label}")
        assert aria_label == "Go North", "North button missing correct aria-label"

        # 4. Center Button (aria-hidden)
        center_btn = page.locator(".nav-center")
        aria_hidden = center_btn.get_attribute("aria-hidden")
        print(f"Center Button aria-hidden: {aria_hidden}")
        assert aria_hidden == "true", "Center button missing aria-hidden='true'"

        # Take a screenshot just to satisfy the tool requirement, though visual check of aria is hard
        page.screenshot(path="verification/accessibility_check.png")
        print("Verification successful!")
        browser.close()

if __name__ == "__main__":
    verify_accessibility()
