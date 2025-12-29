from typing import Dict, Tuple, Optional, Any, TYPE_CHECKING
from core.resolution import Attribute, Skill

if TYPE_CHECKING:
    from engine import GameState, CrewMember, StationMap

class AICache:
    """
    Per-turn cache for AI calculations to avoid redundant lookups.
    Should be reset at the start of every game turn.
    """
    def __init__(self, game_state: 'GameState'):
        self.turn = game_state.turn
        self.player_location = game_state.player.location
        self.player_room = game_state.station_map.get_room_name(*self.player_location)
        self.player_noise = 0
        if hasattr(game_state, 'player'):
             self.player_noise = game_state.player.get_noise_level()
        
        self.power_on = game_state.power_on
        self.room_modifiers: Dict[str, Any] = {}
        self.room_visibility: Dict[str, float] = {}

    def get_room_modifiers(self, room_name: str, game_state: 'GameState'):
        if room_name not in self.room_modifiers:
            if hasattr(game_state, 'room_states'):
                self.room_modifiers[room_name] = game_state.room_states.get_resolution_modifiers(room_name)
            else:
                self.room_modifiers[room_name] = None
        return self.room_modifiers[room_name]

    def get_visibility_modifier(self, room_name: str, game_state: 'GameState'):
        if room_name not in self.room_visibility:
            # Replicate visibility logic from StealthSystem once per room per turn
            mod = 1.0
            if not self.power_on:
                mod *= 0.6 # Placeholder or from config
            
            if hasattr(game_state, 'room_states') and game_state.room_states.has_state(room_name, "dark"):
                mod *= 0.5 # Placeholder or from config
            
            self.room_visibility[room_name] = mod
        return self.room_visibility[room_name]
