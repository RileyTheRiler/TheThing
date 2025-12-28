"""
Tests for command system consistency.

Verifies that:
1. CommandDispatcher commands match the registry
2. HELP output includes all registry commands
3. Tutorial content references valid commands
"""

import pytest
from io import StringIO
import sys

from core.command_registry import COMMAND_REGISTRY, get_command_by_name, get_all_categories
from systems.commands import CommandDispatcher


class TestCommandRegistryConsistency:
    """Test that command registry is the single source of truth."""
    
    def test_registry_has_all_essential_commands(self):
        """Verify registry contains all essential game commands."""
        essential = [
            "MOVE", "LOOK", "TALK", "INTERROGATE", "ATTACK", "TEST",
            "BARRICADE", "STATUS", "INVENTORY", "GET", "DROP",
            "CRAFT", "HIDE", "SAVE", "LOAD", "HELP", "EXIT"
        ]
        
        registry_commands = {cmd.name for cmd in COMMAND_REGISTRY}
        
        for cmd_name in essential:
            assert cmd_name in registry_commands, f"Essential command {cmd_name} missing from registry"
    
    def test_registry_includes_stealth_commands(self):
        """Verify stealth commands are in registry."""
        stealth_commands = ["HIDE", "SNEAK"]
        registry_commands = {cmd.name for cmd in COMMAND_REGISTRY}
        
        for cmd_name in stealth_commands:
            assert cmd_name in registry_commands, f"Stealth command {cmd_name} missing from registry"
    
    def test_registry_includes_crafting_commands(self):
        """Verify crafting commands are in registry."""
        crafting_commands = ["CRAFT"]
        registry_commands = {cmd.name for cmd in COMMAND_REGISTRY}
        
        for cmd_name in crafting_commands:
            assert cmd_name in registry_commands, f"Crafting command {cmd_name} missing from registry"
    
    def test_all_commands_have_metadata(self):
        """Verify all commands have complete metadata."""
        for cmd in COMMAND_REGISTRY:
            assert cmd.name, f"Command missing name: {cmd}"
            assert cmd.description, f"Command {cmd.name} missing description"
            assert cmd.category, f"Command {cmd.name} missing category"
            assert cmd.usage, f"Command {cmd.name} missing usage"
            assert cmd.help_text, f"Command {cmd.name} missing help_text"
    
    def test_get_command_by_name(self):
        """Test command lookup by name."""
        move_cmd = get_command_by_name("MOVE")
        assert move_cmd is not None
        assert move_cmd.name == "MOVE"
        
        # Test alias lookup
        north_cmd = get_command_by_name("N")
        assert north_cmd is not None
        assert north_cmd.name == "MOVE"
    
    def test_categories_are_valid(self):
        """Verify all categories are properly defined."""
        categories = get_all_categories()
        
        expected_categories = [
            "COMBAT", "CRAFTING", "ENVIRONMENT", "FORENSICS",
            "INFORMATION", "INVENTORY", "MOVEMENT", "SOCIAL",
            "STEALTH", "SYSTEM"
        ]
        
        for cat in expected_categories:
            assert cat in categories, f"Expected category {cat} not found in registry"


class TestCommandDispatcherConsistency:
    """Test that CommandDispatcher is consistent with registry."""
    
    def test_dispatcher_registers_all_commands(self):
        """Verify dispatcher has handlers for all registry commands."""
        dispatcher = CommandDispatcher()
        registry_commands = {cmd.name for cmd in COMMAND_REGISTRY}
        
        # Commands that might not have explicit handlers yet
        # (HIDE, SNEAK are new and may not be implemented)
        optional_commands = {"HIDE", "SNEAK"}
        
        for cmd_name in registry_commands:
            if cmd_name in optional_commands:
                # These are allowed to be missing for now
                continue
            
            # Check if command or any alias is registered
            cmd_meta = get_command_by_name(cmd_name)
            found = False
            
            if cmd_name in dispatcher.commands:
                found = True
            else:
                # Check aliases
                for alias in cmd_meta.aliases:
                    if alias in dispatcher.commands:
                        found = True
                        break
            
            # Some commands like HEAT, APPLY, CANCEL are handled in game_loop
            # not in dispatcher, so we'll skip them for now
            legacy_commands = {"HEAT", "APPLY", "CANCEL", "BREAK", "COVER", "RETREAT"}
            if cmd_name in legacy_commands:
                continue
            
            assert found, f"Command {cmd_name} from registry not found in dispatcher"


class TestHelpSystemConsistency:
    """Test that HELP output matches registry."""
    
    def test_help_shows_all_categories(self, capsys):
        """Verify HELP command shows all categories from registry."""
        from game_loop import _show_help
        
        _show_help()
        captured = capsys.readouterr()
        
        categories = get_all_categories()
        for category in categories:
            assert category in captured.out, f"Category {category} not shown in HELP output"
    
    def test_help_topic_shows_category_commands(self, capsys):
        """Verify HELP <TOPIC> shows commands from that category."""
        from game_loop import _show_help
        from core.command_registry import get_commands_by_category
        
        # Test a few categories
        for category in ["MOVEMENT", "COMBAT", "STEALTH", "CRAFTING"]:
            _show_help(category)
            captured = capsys.readouterr()
            
            commands = get_commands_by_category(category)
            for cmd in commands:
                # Check that command name or usage appears in output
                assert (cmd.name in captured.out or cmd.usage in captured.out), \
                    f"Command {cmd.name} from category {category} not in HELP output"


class TestTutorialConsistency:
    """Test that tutorial references valid commands."""
    
    def test_tutorial_mentions_stealth(self):
        """Verify tutorial includes stealth mechanics."""
        from game_loop import _show_tutorial
        
        # Capture tutorial output
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        # Mock input to skip through tutorial
        import builtins
        original_input = builtins.input
        builtins.input = lambda *args: ""
        
        try:
            _show_tutorial()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            builtins.input = original_input
        
        # Check for stealth-related content
        assert "HIDE" in output or "STEALTH" in output, "Tutorial missing stealth content"
    
    def test_tutorial_mentions_crafting(self):
        """Verify tutorial includes crafting mechanics."""
        from game_loop import _show_tutorial
        
        # Capture tutorial output
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        # Mock input to skip through tutorial
        import builtins
        original_input = builtins.input
        builtins.input = lambda *args: ""
        
        try:
            _show_tutorial()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            builtins.input = original_input
        
        # Check for crafting-related content
        assert "CRAFT" in output or "CRAFTING" in output, "Tutorial missing crafting content"
    
    def test_tutorial_command_references_are_valid(self):
        """Verify all commands mentioned in tutorial exist in registry."""
        from game_loop import _show_tutorial
        import re
        
        # Capture tutorial output
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        # Mock input
        import builtins
        original_input = builtins.input
        builtins.input = lambda *args: ""
        
        try:
            _show_tutorial()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            builtins.input = original_input
        
        # Extract command-like words (all caps words that might be commands)
        potential_commands = re.findall(r'\b([A-Z]{3,})\b', output)
        
        # Commands that appear in tutorial
        tutorial_commands = {
            "MOVE", "LOOK", "TALK", "STATUS", "INTERROGATE", "TEST",
            "HEAT", "APPLY", "ATTACK", "COVER", "RETREAT", "BARRICADE",
            "BREAK", "HIDE", "SNEAK", "CRAFT"
        }
        
        registry_commands = {cmd.name for cmd in COMMAND_REGISTRY}
        
        for cmd in tutorial_commands:
            if cmd in potential_commands:
                assert cmd in registry_commands, \
                    f"Tutorial references command {cmd} not in registry"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
