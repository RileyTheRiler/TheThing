import os
import sys
import json
import pytest
import shutil

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from engine import GameState
from systems.persistence import SaveManager
from entities.crew_member import CrewMember
from entities.item import Item
from systems.architect import Difficulty, GameMode

TEST_SAVE_DIR = "tests/test_saves_hardened"

@pytest.fixture
def save_manager():
    if os.path.exists(TEST_SAVE_DIR):
        shutil.rmtree(TEST_SAVE_DIR)
    os.makedirs(TEST_SAVE_DIR)
    manager = SaveManager(save_dir=TEST_SAVE_DIR, game_state_factory=GameState.from_dict)
    yield manager
    if os.path.exists(TEST_SAVE_DIR):
        shutil.rmtree(TEST_SAVE_DIR)

def test_load_missing_optional_keys(save_manager):
    """Test loading a save with missing optional top-level keys."""
    game = GameState()
    full_data = game.to_dict()
    
    # Remove some "optional" keys
    partial_data = full_data.copy()
    keys_to_remove = ["paranoia_level", "journal", "rescue_turns_remaining"]
    for k in keys_to_remove:
        partial_data.pop(k, None)
    
    # Save partial data
    filepath = os.path.join(TEST_SAVE_DIR, "partial.json")
    with open(filepath, 'w') as f:
        json.dump(partial_data, f)
    
    # Load and verify
    loaded_game = save_manager.load_game("partial")
    assert loaded_game is not None
    assert loaded_game.paranoia_level == 0  # Default
    assert loaded_game.journal == []        # Default
    assert loaded_game.rescue_turns_remaining is None # Default

def test_load_malformed_json(save_manager):
    """Test loading a file with malformed JSON syntax."""
    filepath = os.path.join(TEST_SAVE_DIR, "corrupt.json")
    with open(filepath, 'w') as f:
        f.write("{ 'this is not valid json': ,,, }")
    
    loaded_game = save_manager.load_game("corrupt")
    assert loaded_game is None # Should handle error gracefully

def test_load_missing_essential_nested_data(save_manager):
    """Test loading with missing nested data like crew or station_map."""
    game = GameState()
    data = game.to_dict()
    
    # Remove essential nested data
    data.pop("crew", None)
    data.pop("station_map", None)
    
    filepath = os.path.join(TEST_SAVE_DIR, "missing_essential.json")
    with open(filepath, 'w') as f:
        json.dump(data, f)
    
    loaded_game = save_manager.load_game("missing_essential")
    assert loaded_game is not None
    # GameState constructor adds MacReady as fallback if _initialize_crew fails to load from file/data
    assert len(loaded_game.crew) == 1
    assert loaded_game.crew[0].name == "MacReady"
    assert loaded_game.player.name == "MacReady"

def test_load_malformed_crew_member(save_manager):
    """Test loading a crew member with missing or wrong-type fields."""
    game = GameState()
    data = game.to_dict()
    
    # Corrupt one crew member
    data["crew"][0] = {"name": "Corrupt Joe"} # Missing almost everything
    
    filepath = os.path.join(TEST_SAVE_DIR, "corrupt_crew.json")
    with open(filepath, 'w') as f:
        json.dump(data, f)
        
    loaded_game = save_manager.load_game("corrupt_crew")
    assert loaded_game is not None
    corrupt_joe = next((m for m in loaded_game.crew if m.name == "Corrupt Joe"), None)
    assert corrupt_joe is not None
    assert corrupt_joe.role == "None" # Default applied
    assert corrupt_joe.health == 3   # Default applied
    assert corrupt_joe.location == (0, 0) # Default applied

def test_load_invalid_enum_values(save_manager):
    """Test loading with invalid enum strings."""
    game = GameState()
    data = game.to_dict()
    
    data["mode"] = "INVALID_MODE"
    data["difficulty"] = "SUPER_HARD_NOT_REAL"
    data["crew"][0]["stealth_posture"] = "FLYING"
    
    filepath = os.path.join(TEST_SAVE_DIR, "invalid_enums.json")
    with open(filepath, 'w') as f:
        json.dump(data, f)
        
    loaded_game = save_manager.load_game("invalid_enums")
    assert loaded_game is not None
    assert loaded_game.mode == GameMode.INVESTIGATIVE # Default
    assert loaded_game.difficulty == Difficulty.NORMAL # Default
    assert loaded_game.crew[0].stealth_posture.name == "STANDING" # Default
