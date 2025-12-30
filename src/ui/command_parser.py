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
        'throw': 'THROW', 'toss': 'THROW', 'lob': 'THROW',
        'inventory': 'INVENTORY', 'inv': 'INVENTORY', 'items': 'INVENTORY',
        'bag': 'INVENTORY', 'stuff': 'INVENTORY',
        'use': 'USE', # Although not in engine.py blocks explicitly, help text mentions it.
        'craft': 'CRAFT', 'build': 'CRAFT', 'assemble': 'CRAFT', 'make': 'CRAFT',
        
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

        # Tier 6.3: Endings
        'fix': 'REPAIR', 'repair': 'REPAIR', 'patch': 'REPAIR',
        'signal': 'SIGNAL', 'call': 'SIGNAL', 'transmit': 'SIGNAL',
        'fly': 'ESCAPE', 'escape': 'ESCAPE', 'takeoff': 'ESCAPE',

        # Stealth
        'crouch': 'CROUCH', 'duck': 'CROUCH', 'low': 'CROUCH',
        'crawl': 'CRAWL', 'prone': 'CRAWL',
        'stand': 'STAND', 'up': 'STAND', 'rise': 'STAND',
        'hide': 'HIDE', 'stealth': 'HIDE', 'unhide': 'UNHIDE', 'exitcover': 'UNHIDE',
        'sneak': 'SNEAK',
        'vent': 'VENT', 'duct': 'VENT', 'vents': 'VENT',
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
        if not raw:
            return None
            
        normalized = raw.upper()
        
        # Store history (limit to last 50)
        self.command_history.append(raw)
        if len(self.command_history) > 50:
            self.command_history.pop(0)
        
        # Try pattern matching first
        for pattern, template in self.PATTERNS:
            match = re.match(pattern, raw.lower())
            if match:
                groups = match.groups()
                cmd = template.format(*[g.upper() for g in groups])
                return self._parse_simple(cmd)
        
        # Fall back to simple word-based parsing
        parsed = self._parse_simple(normalized)
        if parsed:
            return parsed
            
        # Try fuzzy verb matching if direct parsing failed
        words = normalized.split()
        if words:
            # 1. Fuzzy match intent against all known verbs
            intent = self._fuzzy_match_intent(words[0])
            if intent:
                # Replace the first word with the corrected verb and retry simple parsing
                corrected_command = normalized.replace(words[0], intent, 1)
                return self._parse_simple(corrected_command)

        return None
    
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

    def _fuzzy_match_intent(self, input_verb: str) -> str:
        """
        Find the closest matching verb from known command maps.
        Returns the canonical verb if a high-confidence match is found.
        """
        input_lower = input_verb.lower()
        
        best_verb = None
        best_ratio = 0.0
        
        for synonym, canonical in self.VERB_MAP.items():
            ratio = SequenceMatcher(None, input_lower, synonym).ratio()
            # If input is very short (<=3 chars), require exact match or very high similarity
            if len(input_lower) <= 3:
                if ratio > 0.9: 
                    return synonym
            elif ratio > best_ratio:
                best_ratio = ratio
                best_verb = synonym

        # 80% confidence threshold for auto-execution
        if best_ratio > 0.8:
            return best_verb
        
        return None
    
    def get_help_text(self, command=None):
        """
        Return help text for available commands or specific command details.
        """
        if command:
            return self.get_command_help(command)

        return """
AVAILABLE COMMANDS:
===================
MOVEMENT:    go/move/walk [north/south/east/west] or just n/s/e/w
LOOK:        look/examine/check [name or 'around']
             check [name] for vapor -> Look for breath
SKILLS:      check/roll [skill]
TALK:        talk/speak [to name]
CRAFTING:    craft/build [recipe id]
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

Try 'HELP [COMMAND]' for specific details (e.g., 'HELP REPAIR').
"""

    def get_command_help(self, command):
        """Get detailed help for a specific command."""
        cmd = command.upper()
        
        # Mapping of specific command help
        HELP_DETAILS = {
            "REPAIR": """
COMMAND: REPAIR (Synonyms: FIX, PATCH)
REALIZE: Attempts to fix station equipment (Radio, Helicopter).
REQUIREMENTS:
- Location: Must be in the same room as the equipment (Radio Room or Hangar).
- Items: Usually requires TOOLS and either PARTS or WIRE.
- Turn: Takes 1 turn.
""",
            "SIGNAL": """
COMMAND: SIGNAL (Synonyms: SOS, CAL)
REALIZE: Broadcasts a distress signal to the outside world.
REQUIREMENTS:
- Location: Radio Room.
- State: Radio must be operational (repair it first if needed).
- Outcome: Starts a rescue countdown (approx. 20 turns).
""",
            "ESCAPE": """
COMMAND: ESCAPE (Synonyms: FLY, TAKEOFF)
REALIZE: Attempts to leave the station using the helicopter.
REQUIREMENTS:
- Location: Hangar.
- State: Helicopter must be repaired AND Radio must be operational for navigation.
- Skill: Pilot skill increases success chance.
""",
            "TEST": """
COMMAND: TEST (Synonyms: BLOOD TEST)
REALIZE: Perform a blood test on a crew member to detect infection.
REQUIREMENTS:
- Items: Requires a TEST KIT and a HEAT SOURCE (or FLAMETHROWER).
- Outcome: Reveals if the target is infected. High risk, high reward.
""",
            "CRAFT": """
COMMAND: CRAFT (Synonyms: BUILD, MAKE)
REALIZE: Combine items into more useful equipment.
REQUIREMENTS:
- Recipe: You must have the necessary components in your inventory.
- Turn: Takes 1 turn.
- Tip: Use 'CRAFT LIST' to see recipes.
"""
        }
        
        # Check synonyms if direct match fails
        if cmd not in HELP_DETAILS:
            for verb, canonical in self.VERB_MAP.items():
                if verb.upper() == cmd:
                    cmd = canonical
                    break
        
        return HELP_DETAILS.get(cmd, f"No detailed help available for '{command}'. Try 'HELP' for a list of commands.")
    
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
