"""
CRT Shader/Styling System
Authentic 1982 terminal aesthetics with text crawl, glitches, and scanlines.
"""

import sys
import time
import random

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
    
    # Effects
    GLITCH_CHARS = "▓▒░█▄▀■□▪▫"
    STATIC = ".:;!|+*#@"


class CRTOutput:
    """
    Wraps all text output to simulate a 1982 CRT terminal.
    Features: text crawl, glitches, scanlines, flicker.
    """
    
    def __init__(self, palette="amber", crawl_speed=0.02):
        self.palette = palette
        self.crawl_speed = crawl_speed  # Seconds per character
        self.enabled = True
        self.glitch_level = 0  # 0-100, increases with paranoia
        
        # Set color based on palette
        if palette == "amber":
            self.color = ANSI.AMBER
        elif palette == "green":
            self.color = ANSI.GREEN
        else:
            self.color = ANSI.WHITE
    
    def output(self, text, crawl=False, glitch=False):
        """
        Main output method. Replaces print().
        """
        if not self.enabled:
            print(text)
            return
        
        # Apply color
        colored_text = f"{self.color}{text}{ANSI.RESET}"
        
        if crawl:
            self._crawl_text(colored_text)
        elif glitch:
            self._glitch_text(colored_text)
        else:
            # Apply scanlines for multi-line output
            lines = colored_text.split('\n')
            for i, line in enumerate(lines):
                if i % 2 == 1:
                    # Dim every other line (scanline effect)
                    print(f"{ANSI.DIM}{line}{ANSI.RESET}")
                else:
                    print(line)
    
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
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            if char not in '\n\r':
                time.sleep(self.crawl_speed)
        print()
    
    def _glitch_text(self, text):
        """Apply random glitch effects to text."""
        glitched = []
        for char in text:
            if random.random() < self.glitch_level / 100:
                glitched.append(random.choice(ANSI.GLITCH_CHARS))
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
            static_line = "".join(random.choice(ANSI.STATIC) for _ in range(width))
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
    
    def header(self, text):
        """
        Render a prominent header with box drawing.
        """
        width = len(text) + 4
        border = "═" * width
        
        print(f"{self.color}╔{border}╗{ANSI.RESET}")
        print(f"{self.color}║  {ANSI.BOLD}{text}{ANSI.RESET}{self.color}  ║{ANSI.RESET}")
        print(f"{self.color}╚{border}╝{ANSI.RESET}")
    
    def prompt(self, text="CMD"):
        """
        Render the command prompt with blinking cursor effect.
        """
        return f"{self.color}{ANSI.BOLD}{text}>{ANSI.RESET} "
    
    def warning(self, text):
        """
        High-visibility warning message.
        """
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
