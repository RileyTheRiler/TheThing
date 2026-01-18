from playwright.sync_api import sync_playwright

def verify_frontend(page):
    # Navigate to the page
    page.goto("http://127.0.0.1:5000")

    # Check that duplicates are gone
    # Count "Begin Simulation" buttons
    buttons = page.locator("button:has-text('[ BEGIN SIMULATION ]')")
    count = buttons.count()
    print(f"Begin Simulation buttons: {count}")

    # Check modal close buttons
    # We open a modal to see it
    page.locator("#command-modal").evaluate("node => node.classList.remove('hidden')")

    # Count close buttons in command modal
    close_buttons = page.locator("#command-modal .modal-close")
    close_count = close_buttons.count()
    print(f"Command modal close buttons: {close_count}")

    # Take screenshot
    page.screenshot(path="verification/frontend_fix.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            verify_frontend(page)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()
