"""
Natural Language Command Parser
Translates player text into game commands with fuzzy matching.
"""

import re
from difflib import SequenceMatcher


class CommandParser:
    """
    Parses natural language input into structured game commands.
    Supports fuzzy name matching and verb synonyms.
    """
    
    # Verb synonyms map to canonical commands
    VERB_MAP = {
        # Movement
        'go': 'MOVE', 'walk': 'MOVE', 'run': 'MOVE', 'head': 'MOVE',
        'move': 'MOVE', 'travel': 'MOVE',
        'north': 'MOVE NORTH', 'south': 'MOVE SOUTH', 
        'east': 'MOVE EAST', 'west': 'MOVE WEST',
        'n': 'MOVE NORTH', 's': 'MOVE SOUTH', 
        'e': 'MOVE EAST', 'w': 'MOVE WEST',
        
        # Observation
        'look': 'LOOK', 'examine': 'LOOK', 'inspect': 'LOOK',
        'observe': 'LOOK', 'see': 'LOOK',
        'describe': 'LOOK', 'study': 'LOOK', 'watch': 'LOOK',
        # 'check' -> 'CHECK' (Skill check)
        
        # Communication
        'talk': 'TALK', 'speak': 'TALK', 'ask': 'TALK',
        'chat': 'TALK', 'converse': 'TALK', 'say': 'TALK',
        
        # Items
        'get': 'GET', 'take': 'GET', 'grab': 'GET', 'pick': 'GET',
        'pickup': 'GET', 'acquire': 'GET', 'collect': 'GET',
        'drop': 'DROP', 'discard': 'DROP', 'leave': 'DROP',
        'put': 'DROP', 'place': 'DROP',
        'inventory': 'INVENTORY', 'inv': 'INVENTORY', 'items': 'INVENTORY',
        'bag': 'INVENTORY', 'stuff': 'INVENTORY',
        'use': 'USE', # Although not in engine.py blocks explicitly, help text mentions it.
        
        # Combat
        'attack': 'ATTACK', 'hit': 'ATTACK', 'fight': 'ATTACK',
        'strike': 'ATTACK', 'punch': 'ATTACK', 'kill': 'ATTACK',
        'shoot': 'ATTACK', 'burn': 'ATTACK',
        
        # Investigation
        'tag': 'TAG', 'note': 'TAG', 'mark': 'TAG', 'record': 'TAG',
        'journal': 'JOURNAL', 'notes': 'JOURNAL', 'diary': 'JOURNAL',
        'log': 'LOG', # Evidence log
        'dossier': 'DOSSIER', 'report': 'DOSSIER', 'file': 'DOSSIER',

        # Forensics
        'test': 'TEST', 'heat': 'HEAT', 'apply': 'APPLY', 'cancel': 'CANCEL',
        
        # Social
        'trust': 'TRUST', 'status': 'STATUS',
        
        # System
        'help': 'HELP', 'quit': 'EXIT', 'exit': 'EXIT',
        'advance': 'ADVANCE', 'wait': 'ADVANCE', 'pass': 'ADVANCE',
        'save': 'SAVE', 'load': 'LOAD',

        # Skills/Actions
        'check': 'CHECK', 'roll': 'CHECK', 'skill': 'CHECK',
        'barricade': 'BARRICADE', 'fortify': 'BARRICADE', 'block': 'BARRICADE',
    }
    
    # Direction keywords
    DIRECTIONS = {
        'north': 'NORTH', 'n': 'NORTH', 'up': 'NORTH',
        'south': 'SOUTH', 's': 'SOUTH', 'down': 'SOUTH',
        'east': 'EAST', 'e': 'EAST', 'right': 'EAST',
        'west': 'WEST', 'w': 'WEST', 'left': 'WEST',
    }
    
    # Natural language patterns
    PATTERNS = [
        # "check X for breath" -> LOOK X (special vapor check) - Exception for 'check' mapping
        (r"check\s+(\w+)\s+for\s+(?:breath|vapor|breathing)", "LOOK {0} VAPOR"),
        
        # "go to the X" -> MOVE X (only when "to" is present for room navigation)
        (r"go\s+to\s+(?:the\s+)?(\w+)", "GOTO {0}"),
        
        # "look at X" / "look around"
        (r"look\s+(?:at\s+)?(?:the\s+)?(\w+)", "LOOK {0}"),
        (r"look\s+around", "LOOK"),
        
        # "talk to X" / "speak with X"
        (r"(?:talk|speak)\s+(?:to|with)\s+(?:the\s+)?(\w+)", "TALK {0}"),
        
        # "pick up X" / "take the X"
        (r"(?:pick\s+up|pick|take)\s+(?:the\s+)?(\w+)", "GET {0}"),
        
        # "attack X with Y" -> ATTACK X (weapon auto-selected)
        (r"attack\s+(\w+)\s+with\s+(\w+)", "ATTACK {0}"),
        
        # "what do I have" / "what am I carrying"
        (r"what\s+(?:do\s+I\s+have|am\s+I\s+carrying)", "INVENTORY"),
        
        # "where am I"
        (r"where\s+am\s+I", "STATUS"),
        
        # "who is here" / "who's around"
        (r"who(?:'s|\s+is)\s+(?:here|around|nearby)", "LOOK"),
    ]
    
    def __init__(self, known_names=None):
        """
        Initialize parser with optional list of known character names.
        """
        self.known_names = known_names or []
        self.last_command = None
        self.command_history = []
    
    def set_known_names(self, names):
        """Update the list of known character names for fuzzy matching."""
        self.known_names = [n.upper() for n in names]
    
    def parse(self, raw_input):
        """
        Parse natural language input into a structured command.
        
        Returns:
            dict with 'action', 'target', 'args', 'raw'
            OR None if parsing failed.
        """
        if not raw_input:
            return None
        
        raw = raw_input.strip()
        normalized = raw.upper()
        
        # Store history
        self.command_history.append(raw)
        
        # Try pattern matching first
        for pattern, template in self.PATTERNS:
            match = re.match(pattern, raw.lower())
            if match:
                groups = match.groups()
                cmd = template.format(*[g.upper() for g in groups])
                return self._parse_simple(cmd)
        
        # Fall back to simple word-based parsing
        return self._parse_simple(normalized)
    
    def _parse_simple(self, normalized):
        """
        Parse a normalized command string.
        """
        words = normalized.split()
        if not words:
            return None
        
        first_word = words[0].lower()
        
        # Check for direct verb match
        if first_word in self.VERB_MAP:
            canonical = self.VERB_MAP[first_word]
            
            # Handle compound commands like 'MOVE NORTH'
            if ' ' in canonical:
                parts = canonical.split()
                return {
                    'action': parts[0],
                    'target': parts[1] if len(parts) > 1 else None,
                    'args': [],
                    'raw': normalized
                }
            
            # Handle direction as second word
            target = None
            args = []
            
            if len(words) > 1:
                second = words[1].lower()
                
                # Check for direction
                if second in self.DIRECTIONS:
                    target = self.DIRECTIONS[second]
                else:
                    # Fuzzy match against known names
                    target = self._fuzzy_match_name(words[1])
                    args = words[2:] if len(words) > 2 else []
            
            self.last_command = {
                'action': canonical,
                'target': target,
                'args': args,
                'raw': normalized
            }
            return self.last_command
        
        # Direct direction input
        if first_word in self.DIRECTIONS:
            return {
                'action': 'MOVE',
                'target': self.DIRECTIONS[first_word],
                'args': [],
                'raw': normalized
            }
        
        # Unrecognized command
        return None
    
    def _fuzzy_match_name(self, input_name):
        """
        Find the closest matching name from known names.
        Returns the matched name or the original if no good match.
        """
        if not self.known_names:
            return input_name.upper()
        
        input_upper = input_name.upper()
        
        # Exact match
        if input_upper in self.known_names:
            return input_upper
        
        # Fuzzy match using SequenceMatcher
        best_match = None
        best_ratio = 0.0
        
        for name in self.known_names:
            ratio = SequenceMatcher(None, input_upper, name).ratio()
            if ratio > best_ratio and ratio > 0.6:  # 60% threshold
                best_ratio = ratio
                best_match = name
        
        return best_match if best_match else input_upper
    
    def get_help_text(self):
        """
        Return help text for available commands.
        """
        return """
AVAILABLE COMMANDS:
===================
MOVEMENT:    go/move/walk [north/south/east/west] or just n/s/e/w
LOOK:        look/examine/check [name or 'around']
             check [name] for vapor -> Look for breath
SKILLS:      check/roll [skill]
TALK:        talk/speak [to name]
ITEMS:       get/take [item], drop [item], inventory/inv
COMBAT:      attack/fight [name]
NOTES:       tag [name] [note...], journal, log [item], dossier [name]
SOCIAL:      trust [name], status
SYSTEM:      help, wait/advance, exit, save/load [slot]
FORENSICS:   test [name], heat, apply, cancel, barricade

NATURAL PHRASES:
================
"check Norris for breath"  -> Look for vapor tell
"go to the infirmary"      -> Navigate to room (if adjacent)
"what do I have"           -> Show inventory
"who is here"              -> List nearby crew
"""
    
    def suggest_correction(self, failed_cmd):
        """
        Suggest a correction for a failed command.
        """
        words = failed_cmd.lower().split()
        if not words:
            return None
        
        # Find closest verb
        first = words[0]
        best_verb = None
        best_ratio = 0
        
        for verb in self.VERB_MAP.keys():
            ratio = SequenceMatcher(None, first, verb).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_verb = verb
        
        if best_ratio > 0.5:
            return f"Did you mean '{best_verb}'?"
        return None
