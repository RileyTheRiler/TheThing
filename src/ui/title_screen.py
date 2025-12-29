"""
Title Screen for The Thing
Displays the iconic logo with glitch effects and main menu
"""

import time
import sys
from ui.crt_effects import ANSI


class TitleScreen:
    """
    Title screen with glitched logo effect and menu system
    """

    # ASCII art logo for "THE THING" - stylized, distressed brush-stroke font
    # This matches the rough, pixelated aesthetic from the reference
    LOGO = [
        "                  ___________  __ __ ______",
        "                 /_  __/ __ \\/ // // ____/",
        "              __ / / / / / / // // __/   ",
        "             /_// / / /_/ / // // /___   ",
        "              /_/ /_/\\____/_//_/____/    ",
        "",
        "    ______  __ __ __ _   __ ______ ",
        "   /_  __/ / // // // | / // ____/ ",
        "  __/ /   / // // //  |/ // / __   ",
        " /_/ /   / // // // /|  // /_/ /   ",
        "  /_/   /_//_//_//_/ |_/ \\____/    ",
    ]

    # Glitch overlay positions - these will be the areas that glitch red
    # Format: (line_index, start_col, end_col)
    GLITCH_ZONES = [
        (1, 22, 35),  # Part of "THE"
        (2, 20, 32),  # Part of "THE"
        (7, 10, 25),  # Part of "THING"
        (9, 8, 22),   # Part of "THING"
    ]

    def __init__(self, crt):
        """
        Initialize title screen

        Args:
            crt: CRTOutput instance for rendering
        """
        self.crt = crt
        self.selected_option = 0
        self.menu_options = [
            "BEGIN SIMULATION",
            "ACCESS RECORDS",
            "SYSTEM CONFIG",
            "TERMINATE"
        ]
        self.glitch_active = False
        self.glitch_positions = []

    def _render_header(self):
        """Render environmental status header"""
        header_lines = [
            "STATUS: ISOLATED              TEMP: -58°F         WIND: 90 KNOTS",
            "LOCATION: U.S. OUTPOST 31, ANTARCTICA           DATE: WINTER 1982",
            ""
        ]

        for line in header_lines:
            self.crt.output(line)

    def _render_logo_line(self, line_index, line_text):
        """
        Render a single line of the logo with glitch effect

        Args:
            line_index: Index of the line in LOGO array
            line_text: The text content of the line
        """
        # Check if this line has active glitches
        output = ""
        i = 0

        while i < len(line_text):
            # Check if we're in a glitch zone
            in_glitch = False

            if self.glitch_active:
                for zone in self.GLITCH_ZONES:
                    zone_line, zone_start, zone_end = zone
                    if zone_line == line_index and zone_start <= i < zone_end:
                        in_glitch = True
                        break

            # Render character with appropriate color
            if in_glitch:
                # Red glitch characters
                glitch_chars = ['¥', '§', 'Ø', '@', '#', '█', '▓', '▒']
                import random
                if random.random() < 0.3:  # 30% chance to show glitch char
                    output += f"\033[38;5;196m{random.choice(glitch_chars)}\033[0m"
                else:
                    output += f"\033[38;5;196m{line_text[i]}\033[0m"
            else:
                # Normal green phosphor
                output += f"{ANSI.GREEN}{line_text[i]}{ANSI.RESET}"

            i += 1

        print(output)

    def _render_logo(self):
        """Render the main logo with glitch effects"""
        print()  # Spacing

        for i, line in enumerate(self.LOGO):
            # Center the logo
            padding = " " * 10
            self._render_logo_line(i, padding + line)

        print()  # Spacing

    def _render_radio_chatter(self):
        """Render the radio interference text"""
        chatter = [
            "*CRACKLE* ...anybody read me? Come in, anybody... *STATIC*",
            "(HUMAN LIFE NOT GUARANTEED)"
        ]

        for line in chatter:
            centered = line.center(80)
            self.crt.output(centered, crawl=False)

        print()

    def _render_menu(self):
        """Render menu options with selection indicator"""
        print()

        for i, option in enumerate(self.menu_options):
            if i == self.selected_option:
                # Selected option - highlighted with >
                line = f"    > [ {option} ] <"
            else:
                line = f"      [ {option} ]"

            # Center the option
            centered = line.center(80)
            if i == self.selected_option:
                print(f"{ANSI.BOLD}{ANSI.GREEN}{centered}{ANSI.RESET}")
            else:
                print(f"{ANSI.DIM}{ANSI.GREEN}{centered}{ANSI.RESET}")

        print()

    def _render_system_alert(self):
        """Render system alert footer"""
        print()
        print()

        alert_lines = [
            "SYSTEM ALERT: BIOLOGICAL CONTAMINANT DETECTED IN SECTOR 4.",
            "TRUST STATUS: UNKNOWN. WATCHING: MACREADY, CHILDS, GARRY... [SCANNING]"
        ]

        for line in alert_lines:
            # Blinking/warning effect for alert
            print(f"{ANSI.DIM}{ANSI.GREEN}{line.center(80)}{ANSI.RESET}")

    def render(self):
        """Render the complete title screen"""
        # Clear screen
        print("\033[2J\033[H", end="")

        self._render_header()
        self._render_logo()
        self._render_radio_chatter()
        self._render_menu()
        self._render_system_alert()

    def update_glitch(self, rng):
        """
        Update glitch state - called periodically to animate

        Args:
            rng: Random number generator
        """
        # Randomly toggle glitch on/off
        if rng.random_float() < 0.3:  # 30% chance to toggle
            self.glitch_active = not self.glitch_active

    def show_animated(self, rng, duration=3.0):
        """
        Show title screen with animated glitch effect

        Args:
            rng: Random number generator
            duration: How long to show the animated screen
        """
        start_time = time.time()

        while time.time() - start_time < duration:
            self.update_glitch(rng)
            self.render()
            time.sleep(0.15)  # Fast glitch updates

    def show_interactive(self):
        """
        Show title screen and wait for user input

        Returns:
            Selected menu option (0-3)
        """
        # Show static version
        self.render()

        print()
        print(f"{ANSI.GREEN}Use arrow keys or W/S to navigate, ENTER to select{ANSI.RESET}")
        print(f"{ANSI.GREEN}Or type the number (1-4): {ANSI.RESET}", end="")
        sys.stdout.flush()

        try:
            user_input = input().strip()

            # Check for numeric input
            if user_input.isdigit():
                choice = int(user_input) - 1
                if 0 <= choice < len(self.menu_options):
                    return choice

            # Default to first option
            return 0

        except (EOFError, KeyboardInterrupt):
            return 3  # TERMINATE

    def run(self, rng):
        """
        Run the title screen sequence

        Args:
            rng: Random number generator

        Returns:
            Selected menu option index
        """
        # Show animated intro (3 seconds)
        self.show_animated(rng, duration=3.0)

        # Show interactive menu
        choice = self.show_interactive()

        return choice


def show_title_screen(crt, rng):
    """
    Convenience function to show title screen

    Args:
        crt: CRTOutput instance
        rng: Random number generator

    Returns:
        User's menu selection (0-3)
    """
    title = TitleScreen(crt)
    return title.run(rng)
