"""Combat system for The Thing game.

Provides initiative, cover, and retreat mechanics for tactical combat.
"""

from enum import Enum
from core.resolution import Attribute, Skill, ResolutionSystem
from core.event_system import event_bus, EventType, GameEvent


class CoverType(Enum):
    """Types of cover available during combat."""
    NONE = "None"
    LIGHT = "Light"      # +1 defense die (furniture, doors)
    HEAVY = "Heavy"      # +2 defense dice (walls, machinery)
    FULL = "Full"        # +3 defense dice, can't attack (barricades)


class CombatState(Enum):
    """Current state of combat for a participant."""
    READY = "Ready"
    ENGAGED = "Engaged"
    RETREATING = "Retreating"
    FLED = "Fled"


class CombatResult:
    """Result of a combat action."""

    def __init__(self, success, damage=0, message="", special=None):
        self.success = success
        self.damage = damage
        self.message = message
        self.special = special or {}

    def __str__(self):
        return self.message


class CombatSystem:
    """Handles tactical combat with initiative, cover, and retreat."""

    # Cover bonuses (extra defense dice)
    COVER_BONUS = {
        CoverType.NONE: 0,
        CoverType.LIGHT: 1,
        CoverType.HEAVY: 2,
        CoverType.FULL: 3,
    }

    # Room cover availability
    ROOM_COVER = {
        "Rec Room": [CoverType.LIGHT, CoverType.LIGHT],     # Furniture
        "Infirmary": [CoverType.LIGHT, CoverType.HEAVY],    # Beds, equipment
        "Generator": [CoverType.HEAVY, CoverType.HEAVY],    # Machinery
        "Kennel": [CoverType.LIGHT],                        # Cages
        "Radio Room": [CoverType.LIGHT, CoverType.HEAVY],   # Equipment desk
        "Storage": [CoverType.HEAVY, CoverType.HEAVY, CoverType.LIGHT],  # Crates
        "Lab": [CoverType.LIGHT, CoverType.LIGHT],          # Lab benches
        "Sleeping Quarters": [CoverType.LIGHT, CoverType.LIGHT],  # Bunks
        "Mess Hall": [CoverType.LIGHT, CoverType.LIGHT],    # Tables
    }

    def __init__(self, rng, room_states=None):
        self.rng = rng
        self.room_states = room_states
        self.active_combats = {}  # room_name -> CombatEncounter

    def roll_initiative(self, combatant):
        """Roll initiative for a combatant.

        Initiative = PROWESS + 1d6 + modifiers
        """
        prowess = combatant.attributes.get(Attribute.PROWESS, 1)
        roll = self.rng.roll_d6()

        # Revealed Things get +2 initiative (alien reflexes)
        thing_bonus = 2 if getattr(combatant, 'is_revealed', False) else 0

        # Injured combatants get -1 per missing health
        injury_penalty = max(0, 3 - combatant.health)

        return prowess + roll + thing_bonus - injury_penalty

    def determine_turn_order(self, combatants):
        """Determine combat turn order based on initiative.

        Returns list of (combatant, initiative_score) sorted by initiative.
        """
        initiatives = []
        for c in combatants:
            if c.is_alive:
                init = self.roll_initiative(c)
                initiatives.append((c, init))

        # Sort by initiative descending (highest goes first)
        initiatives.sort(key=lambda x: x[1], reverse=True)
        return initiatives

    def get_available_cover(self, room_name):
        """Get available cover positions in a room."""
        return list(self.ROOM_COVER.get(room_name, [CoverType.LIGHT]))

    def take_cover(self, combatant, room_name, cover_type=None):
        """Attempt to take cover in the room.

        Returns the cover type obtained, or None if no cover available.
        """
        available = self.get_available_cover(room_name)

        if not available:
            return CoverType.NONE

        if cover_type and cover_type in available:
            # Specific cover requested
            available.remove(cover_type)
            return cover_type

        # Take best available cover
        best = max(available, key=lambda c: self.COVER_BONUS[c])
        available.remove(best)
        return best

<<<<<<< HEAD
    def calculate_attack(self, attacker, defender, weapon, cover=CoverType.NONE, room_modifiers=None):
        """Calculate an attack roll with cover and environmental modifiers.
=======
    def calculate_attack(self, attacker, defender, weapon, cover=CoverType.NONE, room_name=None):
        """Calculate an attack roll with cover modifiers.
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503

        Returns CombatResult with outcome.
        """
        # Attack pool: PROWESS + weapon skill
        weapon_skill = getattr(weapon, 'weapon_skill', Skill.MELEE) if weapon else Skill.MELEE
        attr = Skill.get_attribute(weapon_skill)

        base_attack_pool = attacker.attributes.get(attr, 1) + attacker.skills.get(weapon_skill, 0)
        
        # Apply environmental modifiers
        from core.resolution import ResolutionSystem
        attack_pool = ResolutionSystem.resolve_pool(base_attack_pool, [attr, weapon_skill], room_modifiers)

        # Apply environmental modifiers (e.g., darkness, cold)
        modifiers = None
        if self.room_states and room_name:
            modifiers = self.room_states.get_resolution_modifiers(room_name)
            attack_pool = ResolutionSystem.adjust_pool(attack_pool, modifiers.attack_pool)

        # Defense pool: PROWESS + Melee + cover bonus
        base_defense_pool = (
            defender.attributes.get(Attribute.PROWESS, 1) +
            defender.skills.get(Skill.MELEE, 0)
        )
        defense_pool = ResolutionSystem.resolve_pool(base_defense_pool, [Attribute.PROWESS, Skill.MELEE], room_modifiers)
        
        # Add cover bonus after environmental modifiers
        defense_pool += self.COVER_BONUS[cover]

        # Can't attack if defender is in full cover
        if cover == CoverType.FULL:
            return CombatResult(
                success=False,
                message=f"{defender.name} is behind full cover - cannot attack!"
            )

        attack_result = self.rng.calculate_success(attack_pool)
        defense_result = self.rng.calculate_success(defense_pool)

        weapon_name = weapon.name if weapon else "Fists"
        weapon_damage = getattr(weapon, 'damage', 0) if weapon else 0

        if attack_result['success_count'] > defense_result['success_count']:
            net_hits = attack_result['success_count'] - defense_result['success_count']
            total_damage = weapon_damage + net_hits

            # Emit combat event (Tier 2.6 Reporting Pattern)
            event_bus.emit(GameEvent(EventType.COMBAT_LOG, {
                'attacker': attacker.name,
                'target': defender.name,
                'action': f'strikes with {weapon_name}',
                'result': 'HIT',
                'damage': total_damage
            }))

            return CombatResult(
                success=True,
                damage=total_damage,
                message=(
                    f"Attack: {attack_result['success_count']} vs Defense: {defense_result['success_count']} "
                    f"(+{self.COVER_BONUS[cover]} cover)\n"
                    f"HIT! {attacker.name} strikes {defender.name} with {weapon_name} for {total_damage} damage!"
                ),
                special={"net_hits": net_hits, "attack_roll": attack_result, "defense_roll": defense_result}
            )
        else:
            # Emit combat event (Tier 2.6 Reporting Pattern)
            event_bus.emit(GameEvent(EventType.COMBAT_LOG, {
                'attacker': attacker.name,
                'target': defender.name,
                'action': f'attacks with {weapon_name}',
                'result': 'MISS',
                'damage': 0
            }))

            return CombatResult(
                success=False,
                message=(
                    f"Attack: {attack_result['success_count']} vs Defense: {defense_result['success_count']} "
                    f"(+{self.COVER_BONUS[cover]} cover)\n"
                    f"MISS! {defender.name} blocks {attacker.name}'s attack!"
                ),
                special={"attack_roll": attack_result, "defense_roll": defense_result}
            )

    def attempt_retreat(self, combatant, opponents, room_exits):
        """Attempt to retreat from combat.

        Retreat requires a PROWESS check vs average opponent PROWESS.
        Failure results in free attack from all engaged opponents.

        Returns (success, message, exit_direction)
        """
        if not room_exits:
            return False, "No exits available - cannot retreat!", None

        # Combatant's retreat roll
        prowess = combatant.attributes.get(Attribute.PROWESS, 1)
        retreat_result = self.rng.calculate_success(prowess)

        # Opponents try to prevent escape
        total_opposition = 0
        for opp in opponents:
            if opp.is_alive:
                opp_prowess = opp.attributes.get(Attribute.PROWESS, 1)
                total_opposition += opp_prowess

        avg_opposition = max(1, total_opposition // max(1, len([o for o in opponents if o.is_alive])))
        opposition_result = self.rng.calculate_success(avg_opposition)

        if retreat_result['success_count'] >= opposition_result['success_count']:
            # Successful retreat
            exit_dir = self.rng.choose(room_exits)
            return True, f"{combatant.name} successfully retreats {exit_dir}!", exit_dir
        else:
            # Failed retreat - opponents get free attacks
            return False, f"{combatant.name} fails to disengage! Opponents get free attacks!", None

    def process_free_attack(self, attacker, defender, weapon=None, room_name=None):
        """Process a free attack (from failed retreat).

        Free attacks ignore cover.
        """
        return self.calculate_attack(attacker, defender, weapon, CoverType.NONE, room_name)


class CombatEncounter:
    """Represents an active combat encounter in a room."""

    def __init__(self, room_name, combatants, rng, room_states=None):
        self.room_name = room_name
        self.combatants = combatants  # List of CrewMember
        self.rng = rng
        self.combat_system = CombatSystem(rng, room_states)
        self.round = 0
        self.turn_order = []
        self.cover_assignments = {}  # combatant_name -> CoverType
        self.combat_states = {}      # combatant_name -> CombatState
        self.available_cover = self.combat_system.get_available_cover(room_name)

        # Initialize states
        for c in combatants:
            self.combat_states[c.name] = CombatState.ENGAGED

    def start_round(self):
        """Start a new combat round."""
        self.round += 1
        self.turn_order = self.combat_system.determine_turn_order(
            [c for c in self.combatants if c.is_alive and
             self.combat_states.get(c.name) != CombatState.FLED]
        )

        order_str = ", ".join([f"{c.name} ({init})" for c, init in self.turn_order])
        return f"=== COMBAT ROUND {self.round} ===\nInitiative Order: {order_str}"

    def assign_cover(self, combatant_name, cover_type=None):
        """Assign cover to a combatant."""
        if cover_type is None:
            # Auto-assign best available
            if self.available_cover:
                cover_type = max(self.available_cover,
                               key=lambda c: self.combat_system.COVER_BONUS[c])
                self.available_cover.remove(cover_type)
            else:
                cover_type = CoverType.NONE
        elif cover_type in self.available_cover:
            self.available_cover.remove(cover_type)
        else:
            cover_type = CoverType.NONE

        self.cover_assignments[combatant_name] = cover_type
        return cover_type

    def get_combatant_cover(self, combatant_name):
        """Get the cover type for a combatant."""
        return self.cover_assignments.get(combatant_name, CoverType.NONE)

    def is_combat_over(self):
        """Check if combat has ended."""
        alive_humans = [c for c in self.combatants
                       if c.is_alive and not getattr(c, 'is_revealed', False)
                       and self.combat_states.get(c.name) != CombatState.FLED]
        alive_things = [c for c in self.combatants
                       if c.is_alive and getattr(c, 'is_revealed', False)
                       and self.combat_states.get(c.name) != CombatState.FLED]

        # Combat ends if one side is eliminated or fled
        return len(alive_humans) == 0 or len(alive_things) == 0

    def get_status(self):
        """Get current combat status."""
        lines = [f"[COMBAT STATUS - Round {self.round}]"]
        for c in self.combatants:
            if c.is_alive:
                cover = self.get_combatant_cover(c.name)
                state = self.combat_states.get(c.name, CombatState.ENGAGED)
                thing_tag = " [THING]" if getattr(c, 'is_revealed', False) else ""
                lines.append(f"  {c.name}{thing_tag}: HP {c.health}, Cover: {cover.value}, State: {state.value}")
            else:
                lines.append(f"  {c.name}: DEAD")
        return "\n".join(lines)
