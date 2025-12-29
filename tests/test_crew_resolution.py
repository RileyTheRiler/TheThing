
import unittest
from src.engine import CrewMember
from src.core.resolution import ResolutionSystem, Attribute, Skill

class MockRNG:
    def calculate_success(self, pool_size):
        return {
            'success': True,
            'success_count': 1,
            'dice': [6] * pool_size
        }

class TestCrewResolution(unittest.TestCase):
    def setUp(self):
        self.rng = MockRNG()
        self.resolution = ResolutionSystem()
        self.crew = CrewMember("Test", "Tester", "Testy")

    def test_roll_check_injection(self):
        """Test that passing a ResolutionSystem instance works."""
        result = self.crew.roll_check(Attribute.PROWESS, Skill.MELEE, self.rng, self.resolution)
        self.assertTrue(result['success'])
        self.assertEqual(result['success_count'], 1)

    def test_roll_check_fallback(self):
        """Test that fallback to static method works when no system is provided."""
        # Note: This relies on ResolutionSystem.roll_check being static and working with passed RNG
        result = self.crew.roll_check(Attribute.PROWESS, Skill.MELEE, self.rng)
        self.assertTrue(result['success'])
        self.assertEqual(result['success_count'], 1)

if __name__ == '__main__':
    unittest.main()
