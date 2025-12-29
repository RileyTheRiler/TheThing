"""Test stealth commands integration with command parser."""

import pytest
from unittest.mock import MagicMock
from systems.commands import (
    CommandDispatcher, GameContext, HideCommand, CrouchCommand, 
    StandCommand, SneakCommand
)
from entities.crew_member import CrewMember, StealthPosture
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, Skill


@pytest.fixture
def game_context():
    """Create a mock game context for testing."""
    game_state = MagicMock()
    game_state.player = CrewMember("MacReady", "Pilot", "Cynical")
    game_state.player.location = (5, 5)
    game_state.player.attributes = {Attribute.PROWESS: 2}
    game_state.player.skills = {Skill.STEALTH: 2}
    game_state.player.stealth_posture = StealthPosture.STANDING
    
    game_state.station_map = MagicMock()
    game_state.station_map.get_room_name.return_value = "Rec Room"
    game_state.station_map.is_walkable.return_value = True
    
    game_state.room_states = MagicMock()
    game_state.room_states.has_state.return_value = False
    
    game_state.advance_turn = MagicMock()
    
    context = GameContext(game=game_state)
    return context


def test_command_dispatcher_has_stealth_commands():
    """Verify all stealth commands are registered in CommandDispatcher."""
    dispatcher = CommandDispatcher()
    
    assert "HIDE" in dispatcher.commands
    assert "CROUCH" in dispatcher.commands
    assert "STAND" in dispatcher.commands
    assert "SNEAK" in dispatcher.commands


def test_crouch_command(game_context):
    """Test CROUCH command sets posture to CROUCHING."""
    cmd = CrouchCommand()
    
    # Capture events
    messages = []
    def on_message(event):
        messages.append(event.payload.get("text"))
    event_bus.subscribe(EventType.MESSAGE, on_message)
    
    # Execute command
    cmd.execute(game_context, [])
    
    # Verify posture changed
    assert game_context.game.player.stealth_posture == StealthPosture.CROUCHING
    assert len(messages) > 0
    assert "crouch" in messages[0].lower()
    
    event_bus.unsubscribe(EventType.MESSAGE, on_message)


def test_stand_command(game_context):
    """Test STAND command sets posture to STANDING."""
    # Start crouched
    game_context.game.player.stealth_posture = StealthPosture.CROUCHING
    
    cmd = StandCommand()
    
    # Capture events
    messages = []
    def on_message(event):
        messages.append(event.payload.get("text"))
    event_bus.subscribe(EventType.MESSAGE, on_message)
    
    # Execute command
    cmd.execute(game_context, [])
    
    # Verify posture changed
    assert game_context.game.player.stealth_posture == StealthPosture.STANDING
    assert len(messages) > 0
    assert "stand" in messages[0].lower()
    
    event_bus.unsubscribe(EventType.MESSAGE, on_message)


def test_hide_command(game_context):
    """Test HIDE command sets posture to HIDING and advances turn."""
    cmd = HideCommand()
    
    # Capture events
    messages = []
    def on_message(event):
        messages.append(event.payload.get("text"))
    event_bus.subscribe(EventType.MESSAGE, on_message)
    
    # Execute command
    cmd.execute(game_context, [])
    
    # Verify posture changed
    assert game_context.game.player.stealth_posture == StealthPosture.HIDING
    assert len(messages) > 0
    assert "shadow" in messages[0].lower() or "hide" in messages[0].lower()
    
    # Verify turn advanced (hiding takes time)
    game_context.game.advance_turn.assert_called_once()
    
    event_bus.unsubscribe(EventType.MESSAGE, on_message)


def test_sneak_command_north(game_context):
    """Test SNEAK command moves player while crouching."""
    cmd = SneakCommand()
    
    # Mock player move
    game_context.game.player.move = MagicMock(return_value=True)
    
    # Capture events
    movement_events = []
    def on_movement(event):
        movement_events.append(event)
    event_bus.subscribe(EventType.MOVEMENT, on_movement)
    
    # Execute command
    cmd.execute(game_context, ["NORTH"])
    
    # Verify posture set to crouching
    assert game_context.game.player.stealth_posture == StealthPosture.CROUCHING
    
    # Verify movement attempted
    game_context.game.player.move.assert_called_once_with(0, -1, game_context.game.station_map)
    
    # Verify turn advanced
    game_context.game.advance_turn.assert_called_once()
    
    # Verify movement event emitted
    assert len(movement_events) > 0
    
    event_bus.unsubscribe(EventType.MOVEMENT, on_movement)


def test_sneak_command_all_directions(game_context):
    """Test SNEAK works in all cardinal directions."""
    cmd = SneakCommand()
    game_context.game.player.move = MagicMock(return_value=True)
    
    test_cases = [
        ("NORTH", (0, -1)),
        ("N", (0, -1)),
        ("SOUTH", (0, 1)),
        ("S", (0, 1)),
        ("EAST", (1, 0)),
        ("E", (1, 0)),
        ("WEST", (-1, 0)),
        ("W", (-1, 0)),
    ]
    
    for direction, expected_delta in test_cases:
        game_context.game.player.move.reset_mock()
        game_context.game.advance_turn.reset_mock()
        
        cmd.execute(game_context, [direction])
        
        game_context.game.player.move.assert_called_once_with(
            expected_delta[0], expected_delta[1], game_context.game.station_map
        )


def test_sneak_command_blocked(game_context):
    """Test SNEAK command when movement is blocked."""
    cmd = SneakCommand()
    
    # Mock blocked movement
    game_context.game.player.move = MagicMock(return_value=False)
    
    # Capture warnings
    warnings = []
    def on_warning(event):
        warnings.append(event.payload.get("text"))
    event_bus.subscribe(EventType.WARNING, on_warning)
    
    # Execute command
    cmd.execute(game_context, ["NORTH"])
    
    # Verify turn did NOT advance when blocked
    game_context.game.advance_turn.assert_not_called()
    
    # Verify warning emitted
    assert len(warnings) > 0
    assert "blocked" in warnings[0].lower()
    
    event_bus.unsubscribe(EventType.WARNING, on_warning)


def test_sneak_command_no_args(game_context):
    """Test SNEAK command without direction argument."""
    cmd = SneakCommand()
    
    # Capture errors
    errors = []
    def on_error(event):
        errors.append(event.payload.get("text"))
    event_bus.subscribe(EventType.ERROR, on_error)
    
    # Execute command without args
    cmd.execute(game_context, [])
    
    # Verify error emitted
    assert len(errors) > 0
    assert "usage" in errors[0].lower() or "sneak where" in errors[0].lower()
    
    event_bus.unsubscribe(EventType.ERROR, on_error)


def test_dispatcher_stealth_commands(game_context):
    """Test stealth commands through CommandDispatcher."""
    dispatcher = CommandDispatcher()
    
    # Test CROUCH
    dispatcher.dispatch(game_context, "CROUCH")
    assert game_context.game.player.stealth_posture == StealthPosture.CROUCHING
    
    # Test STAND
    dispatcher.dispatch(game_context, "STAND")
    assert game_context.game.player.stealth_posture == StealthPosture.STANDING
    
    # Test HIDE
    dispatcher.dispatch(game_context, "HIDE")
    assert game_context.game.player.stealth_posture == StealthPosture.HIDING
