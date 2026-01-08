from playwright.sync_api import sync_playwright

def verify_aria_labels():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Load the HTML file directly
        import os
        cwd = os.getcwd()
        page.goto(f"file://{cwd}/web/templates/index.html")

        print("Checking ARIA labels...")

        # Check command input
        input_label = page.get_attribute("#command-input", "aria-label")
        print(f"Command input label: {input_label}")
        if input_label != "Enter command":
            print("FAIL: Command input label mismatch")

        # Check search input
        search_label = page.get_attribute("#command-search", "aria-label")
        print(f"Search input label: {search_label}")
        if search_label != "Search commands":
            print("FAIL: Search input label mismatch")

        # Check modal close buttons
        # Note: multiple elements with class modal-close, we check if at least one has the label
        # Actually we need to check specific ones.

        # Command modal close
        cmd_close = page.locator("#command-modal .modal-close")
        cmd_close_label = cmd_close.get_attribute("aria-label")
        print(f"Command modal close label: {cmd_close_label}")

        # Take a screenshot of the command modal to verify visual consistency
        # We need to make it visible first
        page.evaluate("document.getElementById(\"command-modal\").classList.remove(\"hidden\")")
        page.screenshot(path="verification/verification.png")
        print("Screenshot saved to verification/verification.png")

        browser.close()

if __name__ == "__main__":
    verify_aria_labels()
