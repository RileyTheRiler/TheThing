"""
Tests for enhanced crafting recipes including tactical items:
- Noise Maker
- Tripwire Alarm
- Thermal Blanket
- Blood Test Kit
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.entities.item import Item
from src.systems.crafting import CraftingSystem
from src.core.design_briefs import DesignBriefRegistry
from src.core.event_system import event_bus


class DummyMember:
    """Mock character for testing."""
    def __init__(self, name):
        self.name = name
        self.inventory = []

    def add_item(self, item, turn=0):
        self.inventory.append(item)
        if hasattr(item, 'add_history'):
            item.add_history(turn, f"Added to {self.name}")


@pytest.fixture(autouse=True)
def reset_event_bus():
    event_bus.clear()
    yield
    event_bus.clear()


@pytest.fixture
def crafting_data():
    """Load crafting.json and verify enhanced recipes exist."""
    crafting_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'crafting.json')
    with open(crafting_path) as f:
        return json.load(f)


@pytest.fixture
def items_data():
    """Load items.json and verify enhanced items exist."""
    items_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'items.json')
    with open(items_path) as f:
        return json.load(f)


class TestEnhancedRecipesExist:
    """Verify all enhanced recipes are defined in crafting.json."""

    def test_noise_maker_recipe_exists(self, crafting_data):
        """Noise Maker recipe should be defined."""
        recipes = {r['id']: r for r in crafting_data['recipes']}
        assert 'noise_maker' in recipes
        recipe = recipes['noise_maker']
        assert recipe['category'] == 'throwable'
        assert recipe.get('throwable') is True
        assert recipe.get('noise_level', 0) >= 6

    def test_tripwire_alarm_recipe_exists(self, crafting_data):
        """Tripwire Alarm recipe should be defined."""
        recipes = {r['id']: r for r in crafting_data['recipes']}
        assert 'tripwire_alarm' in recipes
        recipe = recipes['tripwire_alarm']
        assert recipe['category'] == 'deployable'
        assert recipe.get('deployable') is True
        assert recipe.get('effect') == 'alerts_on_trigger'

    def test_thermal_blanket_recipe_exists(self, crafting_data):
        """Thermal Blanket recipe should be defined."""
        recipes = {r['id']: r for r in crafting_data['recipes']}
        assert 'thermal_blanket' in recipes
        recipe = recipes['thermal_blanket']
        assert recipe.get('effect') == 'masks_heat'
        assert recipe.get('effect_value', 0) >= 1

    def test_blood_test_kit_recipe_exists(self, crafting_data):
        """Blood Test Kit recipe should be defined."""
        recipes = {r['id']: r for r in crafting_data['recipes']}
        assert 'blood_test_kit' in recipes
        recipe = recipes['blood_test_kit']
        assert recipe.get('effect') == 'portable_test'


class TestEnhancedItemsExist:
    """Verify all required items for enhanced recipes exist."""

    def test_wire_item_exists(self, items_data):
        """Wire item should be defined for crafting."""
        items = {i['id']: i for i in items_data['items']}
        assert 'wire' in items

    def test_cloth_item_exists(self, items_data):
        """Cloth item should be defined for Thermal Blanket."""
        items = {i['id']: i for i in items_data['items']}
        assert 'cloth' in items

    def test_fuel_canister_exists(self, items_data):
        """Fuel Canister should be defined for Thermal Blanket."""
        items = {i['id']: i for i in items_data['items']}
        assert 'fuel_canister' in items

    def test_container_exists(self, items_data):
        """Metal Container should be defined for Blood Test Kit."""
        items = {i['id']: i for i in items_data['items']}
        assert 'container' in items

    def test_rag_item_exists(self, items_data):
        """Rag item should be defined."""
        items = {i['id']: i for i in items_data['items']}
        assert 'rag' in items


class TestRecipeIngredients:
    """Test that recipes have appropriate ingredients."""

    def test_noise_maker_ingredients(self, crafting_data):
        """Noise Maker should require Empty Can and Wire."""
        recipes = {r['id']: r for r in crafting_data['recipes']}
        recipe = recipes['noise_maker']
        ingredients = [i.lower() for i in recipe['ingredients']]
        assert 'empty can' in ingredients or 'wire' in ingredients

    def test_tripwire_alarm_ingredients(self, crafting_data):
        """Tripwire Alarm should require Wire and Empty Can."""
        recipes = {r['id']: r for r in crafting_data['recipes']}
        recipe = recipes['tripwire_alarm']
        ingredients = [i.lower() for i in recipe['ingredients']]
        assert len(ingredients) >= 2

    def test_thermal_blanket_ingredients(self, crafting_data):
        """Thermal Blanket should require Cloth and Fuel."""
        recipes = {r['id']: r for r in crafting_data['recipes']}
        recipe = recipes['thermal_blanket']
        ingredients = [i.lower() for i in recipe['ingredients']]
        assert len(ingredients) >= 2

    def test_blood_test_kit_ingredients(self, crafting_data):
        """Blood Test Kit should require Scalpel, Copper Wire, and Container."""
        recipes = {r['id']: r for r in crafting_data['recipes']}
        recipe = recipes['blood_test_kit']
        ingredients = recipe['ingredients']
        assert len(ingredients) >= 3


class TestCraftingSystemLoadsRecipes:
    """Test that CraftingSystem can load and use enhanced recipes."""

    def test_crafting_system_has_noise_maker(self):
        """CraftingSystem should have noise_maker recipe."""
        crafting = CraftingSystem()  # Uses default path
        assert 'noise_maker' in crafting.recipes
        crafting.cleanup()

    def test_crafting_system_has_tripwire_alarm(self):
        """CraftingSystem should have tripwire_alarm recipe."""
        crafting = CraftingSystem()
        assert 'tripwire_alarm' in crafting.recipes
        crafting.cleanup()

    def test_crafting_system_has_thermal_blanket(self):
        """CraftingSystem should have thermal_blanket recipe."""
        crafting = CraftingSystem()
        assert 'thermal_blanket' in crafting.recipes
        crafting.cleanup()

    def test_crafting_system_has_blood_test_kit(self):
        """CraftingSystem should have blood_test_kit recipe."""
        crafting = CraftingSystem()
        assert 'blood_test_kit' in crafting.recipes
        crafting.cleanup()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
