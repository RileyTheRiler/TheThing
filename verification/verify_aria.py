from playwright.sync_api import sync_playwright, expect
import time

def verify_aria_labels(page):
    # Navigate to the game
    page.goto("http://127.0.0.1:5000")

    # Wait for the game to load (start screen)
    expect(page.locator("#start-screen")).to_be_visible()

    # Click "Begin Simulation" to get to the main game screen
    page.click("text=[ BEGIN SIMULATION ]")

    # Select Difficulty (click EASY)
    page.click("text=[ EASY ]")

    # Wait for game screen
    expect(page.locator("#game-screen")).to_be_visible(timeout=10000)

    # Verify Command Input ARIA
    command_input = page.locator("#command-input")
    expect(command_input).to_have_attribute("aria-label", "Enter command")
    print("Verified: Command Input has aria-label='Enter command'")

    # Verify Navigation Buttons ARIA
    north_btn = page.locator(".nav-btn[data-dir='north']")
    expect(north_btn).to_have_attribute("aria-label", "Go North")
    print("Verified: North Button has aria-label='Go North'")

    west_btn = page.locator(".nav-btn[data-dir='west']")
    expect(west_btn).to_have_attribute("aria-label", "Go West")
    print("Verified: West Button has aria-label='Go West'")

    center_btn = page.locator(".nav-btn.nav-center")
    expect(center_btn).to_have_attribute("aria-hidden", "true")
    print("Verified: Center Button has aria-hidden='true'")

    # Open Command Modal to verify Search Input and Close Button
    # Press '?' key to open command modal
    page.keyboard.press("?")
    expect(page.locator("#command-modal")).to_be_visible()

    search_input = page.locator("#command-search")
    expect(search_input).to_have_attribute("aria-label", "Search commands")
    print("Verified: Command Search has aria-label='Search commands'")

    # Verify Command Modal Close Button
    # Note: There are multiple .modal-close buttons, we need the one inside #command-modal
    close_btn = page.locator("#command-modal .modal-close")
    expect(close_btn).to_have_attribute("aria-label", "Close command reference")
    print("Verified: Command Modal Close Button has aria-label='Close command reference'")

    # Close the modal
    close_btn.click()
    expect(page.locator("#command-modal")).not_to_be_visible()

    # Trigger a toast to verify toast close button
    # We can try to send a command that triggers a toast, e.g., "HELP" triggers a message but maybe not a toast.
    # "SAVE" might trigger a toast? Or we can execute JS.
    page.evaluate("showToast('Test Notification', 'info')")

    toast_close_btn = page.locator(".toast-close")
    expect(toast_close_btn).to_have_attribute("aria-label", "Close notification")
    print("Verified: Toast Close Button has aria-label='Close notification'")

    # Take a screenshot highlighting the command input (focus it)
    command_input.focus()
    page.screenshot(path="verification/aria_verification.png")
    print("Screenshot saved to verification/aria_verification.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            verify_aria_labels(page)
        except Exception as e:
            print(f"Verification failed: {e}")
            page.screenshot(path="verification/failure.png")
        finally:
            browser.close()
