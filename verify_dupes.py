import urllib.request
import re
import sys

try:
    with urllib.request.urlopen('http://127.0.0.1:5000') as response:
        html = response.read().decode('utf-8')

    # Check for duplicate [ BEGIN SIMULATION ] buttons
    begin_sim_count = html.count('[ BEGIN SIMULATION ]')
    print(f"[ BEGIN SIMULATION ] count: {begin_sim_count}")

    # Check for duplicate close buttons in modals
    # We look for the pattern of 3 close buttons in a row
    # <button class="modal-close" ...>✕</button>
    # <button class="modal-close" ...>✕</button>
    # <button class="modal-close" ...>✕</button>

    close_btn_pattern = r'<button class="modal-close"[^>]*>✕</button>\s*<button class="modal-close"[^>]*>✕</button>\s*<button class="modal-close"[^>]*>✕</button>'
    triple_close_matches = len(re.findall(close_btn_pattern, html, re.DOTALL))
    print(f"Triple close button groups: {triple_close_matches}")

    # Check for duplicate input attributes
    input_pattern = r'<input[^>]*placeholder="Enter command..."[^>]*placeholder="Enter command..."'
    double_placeholder = len(re.findall(input_pattern, html))
    print(f"Double placeholder inputs: {double_placeholder}")

    if begin_sim_count > 1 or triple_close_matches > 0 or double_placeholder > 0:
        print("FAIL: Duplicates found")
        sys.exit(1)
    else:
        print("PASS: No duplicates found")
        sys.exit(0)

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
