"""
CRT Shader/Styling System
Authentic 1982 terminal aesthetics with text crawl, glitches, and scanlines.
"""

import sys
import time

# ANSI color codes for terminal effects
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"

    # Monochrome palettes
    AMBER = "\033[38;5;214m"      # Classic amber terminal
    GREEN = "\033[38;5;46m"       # Classic green terminal
    WHITE = "\033[38;5;255m"      # Bright white
    GRAY = "\033[38;5;244m"       # Dimmed gray

    # Colorblind-friendly palettes (high contrast)
    # Using blue-orange color scheme (deuteranopia/protanopia safe)
    CB_BLUE = "\033[38;5;33m"     # Bright blue (safe for most color blindness)
    CB_ORANGE = "\033[38;5;208m"  # Orange (distinguishable from blue)
    CB_CYAN = "\033[38;5;51m"     # Cyan (high visibility)
    CB_YELLOW = "\033[38;5;226m"  # Yellow (high contrast)

    # High contrast mode (for low vision)
    HC_WHITE = "\033[38;5;231m"   # Pure white
    HC_BLACK_BG = "\033[48;5;16m" # Pure black background

    # Functional colors
    DANGER = "\033[38;5;196m"    # Bright Red
    SUCCESS = "\033[38;5;46m"     # Bright Green
    INFO = "\033[38;5;39m"        # Light Blue
    WARNING = "\033[38;5;214m"     # Orange/Amber
    
    # Semantic Colors (Tier 7)
    VICTORY = "\033[38;5;220m"    # Gold
    MUTINY = "\033[38;5;129m"     # Purple
    WHISPER = "\033[38;5;241m"    # Dark Gray
    SHOUT = "\033[1;38;5;196m"    # Bold Red
    QUOTE = "\033[3;38;5;51m"     # Italic Cyan

    # Effects
    GLITCH_CHARS = "#@%&?!<>*+=~"
    STATIC = ".:;!|+*#@"


# Available palette configurations
PALETTES = {
    "amber": {
        "primary": ANSI.AMBER,
        "description": "Classic amber CRT terminal (default)"
    },
    "green": {
        "primary": ANSI.GREEN,
        "description": "Classic green phosphor terminal"
    },
    "white": {
        "primary": ANSI.WHITE,
        "description": "Modern white terminal"
    },
    "colorblind": {
        "primary": ANSI.CB_CYAN,
        "description": "High contrast blue/cyan (colorblind-friendly)"
    },
    "high-contrast": {
        "primary": ANSI.HC_WHITE,
        "description": "Maximum contrast white on black"
    }
}


class CRTOutput:
    """
    Wraps all text output to simulate a 1982 CRT terminal.
    Features: text crawl, glitches, scanlines, flicker.
    """

    def __init__(self, palette="amber", crawl_speed=0.02, rng=None):
        self.palette = palette
        self.crawl_speed = crawl_speed  # Seconds per character
        self.enabled = True
        self.glitch_level = 0  # 0-100, increases with paranoia
        
        from systems.architect import RandomnessEngine
        self.rng = rng or RandomnessEngine()
        
        # Web/Server Capture Support
        self.capture_mode = False
        self.buffer = []

        # Set color based on palette
        self.set_palette(palette)

    def set_palette(self, palette_name):
        """Set the color palette. Supports colorblind-friendly options."""
        self.palette = palette_name

        if palette_name in PALETTES:
            self.color = PALETTES[palette_name]["primary"]
        elif palette_name == "amber":
            self.color = ANSI.AMBER
        elif palette_name == "green":
            self.color = ANSI.GREEN
        else:
            self.color = ANSI.WHITE

    @staticmethod
    def get_available_palettes():
        """Return list of available palette names and descriptions."""
        return {name: config["description"] for name, config in PALETTES.items()}
    
    def start_capture(self):
        """Start buffering output instead of printing to stdout."""
        self.capture_mode = True
        self.buffer = []

    def stop_capture(self):
        """Stop buffering and return collected messages."""
        messages = self.buffer
        self.capture_mode = False
        self.buffer = []
        return messages

    def output(self, text, crawl=False, glitch=False):
        """
        Main output method. Replaces print().
        """
        if not self.enabled:
            if self.capture_mode:
                self.buffer.append(text)
            else:
                print(text)
            return
        
        # Apply color
        colored_text = f"{self.color}{text}{ANSI.RESET}"
        
        if crawl:
            self._crawl_text(colored_text)
        elif glitch:
            self._glitch_text(colored_text)
        else:
            if self.capture_mode:
                self.buffer.append(text)
            else:
                # Apply scanlines for multi-line output
                lines = colored_text.split('\n')
                for i, line in enumerate(lines):
                    if i % 2 == 1:
                        # Dim every other line (scanline effect)
                        print(f"{ANSI.DIM}{line}{ANSI.RESET}")
                    else:
                        print(line)

    def event(self, text, type="info", crawl=True):
        """
        Output a game event with specific coloring.
        Types: 'danger', 'success', 'info', 'warning', 'system'
        """
        color_map = {
            "danger": ANSI.DANGER,
            "success": ANSI.SUCCESS,
            "info": ANSI.INFO,
            "warning": ANSI.WARNING,
            "system": self.color
        }
        
        selected_color = color_map.get(type, self.color)
        prefix = {
            "danger": "[!!] ",
            "success": "[OK] ",
            "info": "[i] ",
            "warning": "[!] ",
            "system": ":: ",
            "victory": "*** ",
            "mutiny": "!!! ",
            "quote": "" 
        }.get(type, "")

        text_style = {
            "victory": ANSI.VICTORY + ANSI.BOLD,
            "mutiny": ANSI.MUTINY + ANSI.BLINK,
            "quote": ANSI.QUOTE,
            "shout": ANSI.SHOUT
        }.get(type, selected_color)

        message = f"{prefix}{text}"
        
        if self.capture_mode:
            self.buffer.append(f"[{type.upper()}] {text}")
            return

        if crawl:
            # Use specific speed for events
            speed = 0.04 if type in ["danger", "mutiny"] else 0.02
            self._crawl_with_color(message, text_style, speed)
        else:
            print(f"{text_style}{message}{ANSI.RESET}")

    def _crawl_with_color(self, text, color, speed):
        """Crawl text with a specific color and speed."""
        sys.stdout.write(color)
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            if char in '.!?':
                time.sleep(speed * 3)
            elif char == ' ':
                time.sleep(speed * 0.5)
            else:
                time.sleep(speed)
        print(ANSI.RESET)
    
    def crawl(self, text, speed=None):
        """
        Typewriter effect - reveal text character by character.
        """
        if speed is None:
            speed = self.crawl_speed
        
        colored = f"{self.color}"
        for char in text:
            sys.stdout.write(colored + char)
            sys.stdout.flush()
            
            # Variable speed: faster for spaces, slower for punctuation
            if char in '.!?':
                time.sleep(speed * 3)
            elif char == ' ':
                time.sleep(speed * 0.5)
            elif char == '\n':
                time.sleep(speed * 2)
            else:
                time.sleep(speed)
        
        print(ANSI.RESET)
    
    def _crawl_text(self, text):
        """Internal crawl with color already applied."""
        if self.capture_mode:
            # For capture mode, we just strip ANSI and buffer it
            import re
            clean_text = re.sub(r'\033\[[0-9;]*m', '', text)
            self.buffer.append(clean_text)
            return

        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            if char not in '\n\r':
                time.sleep(self.crawl_speed)
        print()

    def crawl_pause(self, seconds=1.0):
        """Insert a dramatic pause in output."""
        if not self.enabled or self.capture_mode:
            return
        time.sleep(seconds)
    
    def _glitch_text(self, text):
        """Apply random glitch effects to text."""
        glitched = []
        for char in text:
            if self.rng.random_float() < self.glitch_level / 100:
                glitched.append(self.rng.choose(ANSI.GLITCH_CHARS))
            else:
                glitched.append(char)
        print("".join(glitched))
    
    def glitch(self, intensity=50, duration=0.5):
        """
        Screen glitch effect - triggered by paranoia/events.
        """
        if not self.enabled:
            return
        
        start = time.time()
        while time.time() - start < duration:
            # Generate random static line
            width = 60
            static_line = "".join(self.rng.choose(ANSI.STATIC) for _ in range(width))
            sys.stdout.write(f"\r{self.color}{static_line}{ANSI.RESET}")
            sys.stdout.flush()
            time.sleep(0.05)
        
        # Clear the glitch line
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()
    
    def flicker(self, count=3, interval=0.1):
        """
        Screen flicker effect - for power outages.
        """
        if not self.enabled:
            return
        
        for _ in range(count):
            # "Turn off" - print empty lines
            print("\033[2J\033[H", end="")  # Clear screen
            time.sleep(interval)
            # "Turn on" - will be followed by redraw
            time.sleep(interval)
    
    def scanline(self, text):
        """
        Apply scanline dimming effect to text block.
        """
        lines = text.split('\n')
        result = []
        for i, line in enumerate(lines):
            if i % 2 == 1:
                result.append(f"{ANSI.DIM}{line}{ANSI.RESET}")
            else:
                result.append(f"{self.color}{line}{ANSI.RESET}")
        return '\n'.join(result)
    
    def header(self, text, style="standard"):
        """
        Render a prominent header with various box styles.
        """
        if style == "danger":
            self.header_danger(text)
            return
        elif style == "success":
            self.header_success(text)
            return

        width = len(text) + 4
        border = "=" * width
        
        print(f"{self.color}+{border}+{ANSI.RESET}")
        print(f"{self.color}|  {ANSI.BOLD}{text}{ANSI.RESET}{self.color}  |{ANSI.RESET}")
        print(f"{self.color}+{border}+{ANSI.RESET}")

    def header_danger(self, text):
        """Dramatic danger header."""
        width = len(text) + 6
        border = "#" * width
        print(f"{ANSI.DANGER}{ANSI.BOLD}{border}{ANSI.RESET}")
        print(f"{ANSI.DANGER}{ANSI.BOLD}#  {text.upper()}  #{ANSI.RESET}")
        print(f"{ANSI.DANGER}{ANSI.BOLD}{border}{ANSI.RESET}")

    def header_success(self, text):
        """Success header."""
        width = len(text) + 6
        border = "*" * width
        print(f"{ANSI.SUCCESS}{ANSI.BOLD}{border}{ANSI.RESET}")
        print(f"{ANSI.SUCCESS}{ANSI.BOLD}*  {text}  *{ANSI.RESET}")
        print(f"{ANSI.SUCCESS}{ANSI.BOLD}{border}{ANSI.RESET}")

    def ascii_art(self, art_type):
        """Display ASCII art for major events."""
        arts = {
            "the_thing": [
                " _______ _    _ ______   _______ _    _ _____ _   _  _____ ",
                "|__   __| |  | |  ____| |__   __| |  | |_   _| \ | |/ ____|",
                "   | |  | |__| | |__       | |  | |__| | | | |  \| | |  __ ",
                "   | |  |  __  |  __|      | |  |  __  | | | | . ` | | |_ |",
                "   | |  | |  | | |____     | |  | |  | |_| |_| |\  | |__| |",
                "   |_|  |_|  |_|______|    |_|  |_|  |_|_____|_| \_|\_____|"
            ],
            "station_31": [
                "   _____ _______       _______ _____  ____  _   _   _________ ",
                "  / ____|__   __|/\\   |__   __|_   _|/ __ \\| \\ | | |___  / _ \\",
                " | (___    | |  /  \\     | |    | | | |  | |  \\| |    / /| | | |",
                "  \\___ \\   | | / /\\ \\    | |    | | | |  | | . ` |   / / | | | |",
                "  ____) |  | |/ ____ \\   | |   _| |_| |__| | |\\  |  / /__| |_| |",
                " |_____/   |_/_/    \\_\\  |_|  |_____|\\____/|_| \\_| /_____|\\___/ "
            ]
        }
        
        lines = arts.get(art_type, [])
        color = ANSI.DANGER if art_type == "the_thing" else self.color
        for line in lines:
            print(f"{color}{line}{ANSI.RESET}")
            time.sleep(0.05)
    
    def prompt(self, text="CMD"):
        """
        Render the command prompt with blinking cursor effect.
        """
        return f"{self.color}{ANSI.BOLD}{text}>{ANSI.RESET} "
    
    def warning(self, text):
        """
        High-visibility warning message.
        """
        if self.capture_mode:
            self.buffer.append(f"[WARNING] {text}")
        else:
            print(f"{ANSI.BLINK}{self.color}[!] {text}{ANSI.RESET}")
    
    def status_bar(self, turn, temp, location, power):
        """
        Render the HUD status bar.
        """
        power_str = f"{ANSI.BOLD}ON{ANSI.RESET}" if power else f"{ANSI.DIM}OFF{ANSI.RESET}"
        bar = f"[TURN {turn:03d}] TEMP: {temp:+03d}C | LOC: {location} | POWER: {power_str}"
        print(f"{self.color}{bar}{ANSI.RESET}")
    
    def set_glitch_level(self, paranoia):
        """
        Adjust glitch intensity based on paranoia level.
        """
        self.glitch_level = min(100, max(0, paranoia))
    
    def boot_sequence(self):
        """
        Display terminal boot sequence for immersion.
        """
        boot_lines = [
            "ROS-31 TERMINAL SYSTEM v2.14",
            "INITIALIZING...",
            "MEMORY CHECK: 64KB OK",
            "STATION UPLINK: CONNECTED",
            "ANTARCTIC RESEARCH STATION 31",
            "DATE: WINTER 1982",
            "",
            "TYPE 'HELP' FOR COMMANDS",
            "================================"
        ]
        
        self.header("SYSTEM BOOT")
        for line in boot_lines:
            self.crawl(line, speed=0.01)
            time.sleep(0.1)
