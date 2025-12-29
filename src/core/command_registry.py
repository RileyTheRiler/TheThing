from dataclasses import dataclass, field
from typing import List, Optional, Set

@dataclass
class CommandMetadata:
    """Metadata for a single game command."""
    name: str
    aliases: List[str]
    description: str
    category: str
    usage: str
    help_text: str

COMMAND_REGISTRY: List[CommandMetadata] = [
    # MOVEMENT
    CommandMetadata(
        name="MOVE",
        aliases=["N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST"],
        description="Move in a direction.",
        category="MOVEMENT",
        usage="MOVE <DIR> or <DIR>",
        help_text="Move in a cardinal direction (NORTH, SOUTH, EAST, WEST)."
    ),
    CommandMetadata(
        name="LOOK",
        aliases=["L", "EXAMINE", "X"],
        description="Look at room or item.",
        category="MOVEMENT",
        usage="LOOK [target]",
        help_text="Describe the current room or a specific item/person."
    ),

    # COMBAT
    CommandMetadata(
        name="ATTACK",
        aliases=["KILL", "FIGHT"],
        description="Attack a target.",
        category="COMBAT",
        usage="ATTACK <TARGET> [WITH <WEAPON>]",
        help_text="Initiate combat with a target. You can specify a weapon."
    ),
    CommandMetadata(
        name="COVER",
        aliases=[],
        description="Take cover.",
        category="COMBAT",
        usage="COVER",
        help_text="Take cover to increase defense against ranged attacks."
    ),
    CommandMetadata(
        name="RETREAT",
        aliases=["RUN", "FLEE"],
        description="Flee from combat.",
        category="COMBAT",
        usage="RETREAT",
        help_text="Attempt to escape from the current room during combat."
    ),
    CommandMetadata(
        name="BARRICADE",
        aliases=["BLOCK"],
        description="Barricade the room.",
        category="COMBAT",
        usage="BARRICADE",
        help_text="Reinforce the room to delay entry by enemies."
    ),
    CommandMetadata(
        name="BREAK",
        aliases=["SMASH"],
        description="Break a barricade.",
        category="COMBAT",
        usage="BREAK <DIR>",
        help_text="Attempt to break through a barricade in a direction."
    ),

    # FORENSICS
    CommandMetadata(
        name="TEST",
        aliases=["BLOODTEST"],
        description="Perform a blood test.",
        category="FORENSICS",
        usage="TEST <suspect>",
        help_text="Test a suspect's blood. Requires SCALPEL, WIRE, and heating."
    ),
    CommandMetadata(
        name="HEAT",
        aliases=[],
        description="Heat the copper wire.",
        category="FORENSICS",
        usage="HEAT",
        help_text="Heat the copper wire for the blood test."
    ),
    CommandMetadata(
        name="APPLY",
        aliases=[],
        description="Apply hot wire to blood.",
        category="FORENSICS",
        usage="APPLY",
        help_text="Apply the heated wire to the blood sample."
    ),
    CommandMetadata(
        name="TAG",
        aliases=[],
        description="Tag forensic evidence.",
        category="FORENSICS",
        usage="TAG <name> <category> <note>",
        help_text="Log a forensic note about a character."
    ),
    CommandMetadata(
        name="DOSSIER",
        aliases=[],
        description="View forensic dossier.",
        category="FORENSICS",
        usage="DOSSIER <name>",
        help_text="View collected forensic data on a character."
    ),
    CommandMetadata(
        name="LOG",
        aliases=[],
        description="View evidence log.",
        category="FORENSICS",
        usage="LOG <item>",
        help_text="View the history of an item."
    ),

    # SOCIAL
    CommandMetadata(
        name="TALK",
        aliases=["SPEAK"],
        description="Talk to someone.",
        category="SOCIAL",
        usage="TALK <target>",
        help_text="Talk to a character in the room."
    ),
    CommandMetadata(
        name="INTERROGATE",
        aliases=["QUESTION"],
        description="Interrogate a suspect.",
        category="SOCIAL",
        usage="INTERROGATE <target> [TOPIC]",
        help_text="Aggressively question a suspect."
    ),
    CommandMetadata(
        name="ACCUSE",
        aliases=[],
        description="Accuse someone of being The Thing.",
        category="SOCIAL",
        usage="ACCUSE <target>",
        help_text="Accuse a character. Can trigger a standoff."
    ),
    CommandMetadata(
        name="TRUST",
        aliases=[],
        description="View trust scores.",
        category="SOCIAL",
        usage="TRUST [target]",
        help_text="View your trust in others, or their trust in you."
    ),

    # INVENTORY
    CommandMetadata(
        name="INVENTORY",
        aliases=["I", "INV"],
        description="Check inventory.",
        category="INVENTORY",
        usage="INVENTORY",
        help_text="List items you are carrying."
    ),
    CommandMetadata(
        name="GET",
        aliases=["TAKE", "GRAB", "PICKUP"],
        description="Pick up an item.",
        category="INVENTORY",
        usage="GET <item>",
        help_text="Pick up an item from the room."
    ),
    CommandMetadata(
        name="DROP",
        aliases=[],
        description="Drop an item.",
        category="INVENTORY",
        usage="DROP <item>",
        help_text="Drop an item into the current room."
    ),
    CommandMetadata(
        name="GIVE",
        aliases=[],
        description="Give an item.",
        category="INVENTORY",
        usage="GIVE <item> TO <target>",
        help_text="Give an item to another character."
    ),

    # STEALTH
    CommandMetadata(
        name="HIDE",
        aliases=[],
        description="Hide in the room.",
        category="STEALTH",
        usage="HIDE",
        help_text="Attempt to hide in the current room. Affected by lighting."
    ),
    CommandMetadata(
        name="VENT",
        aliases=["DUCT"],
        description="Enter or crawl through ventilation ducts.",
        category="STEALTH",
        usage="VENT ENTER|EXIT|<DIR>",
        help_text="Enter a vent at an entry point, crawl to adjacent vent nodes, or exit back into a room."
    ),
    CommandMetadata(
        name="SNEAK",
        aliases=[],
        description="Move stealthily.",
        category="STEALTH",
        usage="SNEAK <DIR>",
        help_text="Move to an adjacent room without being detected."
    ),

    # CRAFTING
    CommandMetadata(
        name="CRAFT",
        aliases=["MAKE", "BUILD"],
        description="Craft an item.",
        category="CRAFTING",
        usage="CRAFT <recipe>",
        help_text="Combine items to create a new item."
    ),

    # SYSTEM
    CommandMetadata(
        name="HELP",
        aliases=["?"],
        description="Show help.",
        category="SYSTEM",
        usage="HELP [topic]",
        help_text="Show list of commands or help for a specific topic."
    ),
    CommandMetadata(
        name="STATUS",
        aliases=[],
        description="Check status.",
        category="SYSTEM",
        usage="STATUS",
        help_text="Check your health, stress, and conditions."
    ),
    CommandMetadata(
        name="SAVE",
        aliases=[],
        description="Save the game.",
        category="SYSTEM",
        usage="SAVE [slot]",
        help_text="Save your current progress."
    ),
    CommandMetadata(
        name="LOAD",
        aliases=[],
        description="Load a game.",
        category="SYSTEM",
        usage="LOAD [slot]",
        help_text="Load a saved game."
    ),
    CommandMetadata(
        name="EXIT",
        aliases=["QUIT"],
        description="Exit the game.",
        category="SYSTEM",
        usage="EXIT",
        help_text="Quit to the main menu."
    ),
    CommandMetadata(
        name="WAIT",
        aliases=["Z"],
        description="Wait one turn.",
        category="SYSTEM",
        usage="WAIT",
        help_text="Pass time without taking an action."
    ),
    CommandMetadata(
        name="SETTINGS",
        aliases=["CONFIG"],
        description="Change settings.",
        category="SYSTEM",
        usage="SETTINGS <key> <value>",
        help_text="Modify game settings."
    )
]

def get_command_by_name(name: str) -> Optional[CommandMetadata]:
    """Find a command by name or alias (case-insensitive)."""
    name = name.upper()
    for cmd in COMMAND_REGISTRY:
        if cmd.name == name or name in cmd.aliases:
            return cmd
    return None

def get_commands_by_category(category: str) -> List[CommandMetadata]:
    """Get all commands in a specific category."""
    category = category.upper()
    return [cmd for cmd in COMMAND_REGISTRY if cmd.category == category]

def get_all_categories() -> List[str]:
    """Get a list of all unique command categories."""
    categories = {cmd.category for cmd in COMMAND_REGISTRY}
    return sorted(list(categories))
