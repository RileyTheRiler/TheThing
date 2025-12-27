from typing import List, Optional

from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, Skill


class StealthSystem:
    """
    Handles stealth encounters by reacting to TURN_ADVANCE events.
    Emits reporting events so the UI can surface outcomes without direct calls.
    """

    def __init__(self, design_registry: Optional[DesignBriefRegistry] = None):
        self.design_registry = design_registry or DesignBriefRegistry()
        self.config = self.design_registry.get_brief("stealth")
        self.cooldown = 0
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def _detect_candidates(self, crew) -> List:
        """Return infected crew sharing a room with the player."""
        return [m for m in crew if getattr(m, "is_infected", False) and getattr(m, "is_alive", True)]

    def on_turn_advance(self, event: GameEvent):
        if self.cooldown > 0:
            self.cooldown -= 1

        game_state = event.payload.get("game_state")
        rng = event.payload.get("rng")
        if not game_state or rng is None:
            return

        player = getattr(game_state, "player", None)
        crew = getattr(game_state, "crew", [])
        station_map = getattr(game_state, "station_map", None)
        room_states = getattr(game_state, "room_states", None)
        if not player or not station_map:
            return

        room = station_map.get_room_name(*player.location)
        nearby_infected = [
            m for m in self._detect_candidates(crew)
            if getattr(m, "location", None) == player.location
        ]

        if not nearby_infected or self.cooldown > 0:
            return

        opponent = nearby_infected[0]
        
        # 1. Subject Pool (Player Stealth)
        prowess = player.attributes.get(Attribute.PROWESS, 1) if hasattr(player, "attributes") else 2
        stealth = player.skills.get(Skill.STEALTH, 0) if hasattr(player, "skills") else 0
        subject_pool = prowess + stealth

        # 2. Observer Pool (Infected NPC Perception)
        logic = opponent.attributes.get(Attribute.LOGIC, 1)
        observation = opponent.skills.get(Skill.OBSERVATION, 0)
        observer_pool = logic + observation

        # 3. Modifiers (Posture and Environment)
        from entities.crew_member import StealthPosture
        
        posture = getattr(player, "stealth_posture", StealthPosture.STANDING)
        if posture == StealthPosture.CROUCHING:
            subject_pool += 1
        elif posture == StealthPosture.CRAWLING:
            subject_pool += 2
        elif posture == StealthPosture.HIDING:
            subject_pool += 4

        # Fetch room modifiers
        room_modifiers = room_states.get_roll_modifiers(room) if room_states else {}
        
        # Apply modifiers using ResolutionSystem
        from core.resolution import ResolutionSystem
        subject_pool = ResolutionSystem.resolve_pool(subject_pool, [Skill.STEALTH], room_modifiers)
        observer_pool = ResolutionSystem.resolve_pool(observer_pool, [Skill.OBSERVATION], room_modifiers)
        
        # Enforce minimum pool of 1
        subject_pool = max(1, subject_pool)
        observer_pool = max(1, observer_pool)

        # 4. Resolution
        from core.resolution import ResolutionSystem
        res = ResolutionSystem()
        
        subject_result = res.roll_check(subject_pool, rng)
        observer_result = res.roll_check(observer_pool, rng)
        
        # Success = Subject (Player) has more successes than Observer (NPC)
        # Tie goes to observer (detection)
        player_evaded = subject_result['success_count'] > observer_result['success_count']
        
        payload = {
            "room": room,
            "opponent": opponent.name,
            "outcome": "evaded" if player_evaded else "detected",
            "player_successes": subject_result['success_count'],
            "opponent_successes": observer_result['success_count']
        }
        event_bus.emit(GameEvent(EventType.STEALTH_REPORT, payload))
        
        # Emit AI perception event for other systems to hook into
        event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, payload))

        if not player_evaded:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"{opponent.name} corners you in the {room}!"
            }))
        else:
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"You stay hidden from {opponent.name} in the {room}."
            }))

        self.cooldown = self.config.get("cooldown_turns", 1)
