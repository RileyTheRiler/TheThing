import os
import sys

import pytest

TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Add repository root and src directory to path for absolute imports
sys.path.insert(0, TEST_ROOT)
sys.path.insert(0, os.path.join(TEST_ROOT, "src"))

from core.event_system import EventType, event_bus
from engine import GameState
from entities.crew_member import CrewMember
from systems.social import LynchMobSystem, SocialThresholds, TrustMatrix


@pytest.fixture
def crew():
    team = [
        CrewMember("MacReady", "Pilot", "cautious"),
        CrewMember("Childs", "Mechanic", "aggressive"),
        CrewMember("Norris", "Geologist", "nervous"),
    ]
    for member in team:
        member.location = (5, 5)
    return team


def test_trust_threshold_events_on_decay_and_regain(crew):
    thresholds = SocialThresholds(trust_thresholds=[25, 50, 75])
    trust = TrustMatrix(crew, thresholds=thresholds)

    events = []

    def on_threshold(event):
        events.append(event)

    event_bus.subscribe(EventType.TRUST_THRESHOLD, on_threshold)

    trust.modify_trust("MacReady", "Childs", -40)
    assert events, "Trust decay should emit a threshold event."
    assert events[-1].payload["direction"] == "down"
    assert events[-1].payload["bucket"] == "critical"

    trust.modify_trust("MacReady", "Childs", 50)
    assert events[-1].payload["direction"] == "up"
    assert events[-1].payload["bucket"] in {"guarded", "steady", "trusted", "bonded"}

    event_bus.unsubscribe(EventType.TRUST_THRESHOLD, on_threshold)


def test_paranoia_threshold_events_fire_on_crossing():
    thresholds = SocialThresholds(paranoia_thresholds=[10, 50, 90])
    game = GameState(seed=7, thresholds=thresholds)

    captured = []

    def on_paranoia(event):
        captured.append(event)

    event_bus.subscribe(EventType.PARANOIA_THRESHOLD, on_paranoia)

    game.paranoia_level = 55
    assert captured, "Paranoia increase should emit a threshold event."
    assert captured[-1].payload["direction"] == "up"
    assert captured[-1].payload["bucket"] in {"guarded", "steady", "trusted", "bonded"}

    game.paranoia_level = 5
    assert captured[-1].payload["direction"] == "down"
    assert captured[-1].payload["bucket"] == "critical"

    event_bus.unsubscribe(EventType.PARANOIA_THRESHOLD, on_paranoia)


def test_lynch_mob_requires_trust_and_paranoia_thresholds(crew):
    thresholds = SocialThresholds(lynch_average_threshold=25, lynch_paranoia_trigger=30)
    trust = TrustMatrix(crew, thresholds=thresholds)
    lynch_mob = LynchMobSystem(trust, thresholds=thresholds)

    for member in crew:
        if member.name != "Norris":
            trust.modify_trust(member.name, "Norris", -40)

    lynch_events = []

    def on_lynch(event):
        lynch_events.append(event)

    event_bus.subscribe(EventType.LYNCH_MOB_TRIGGER, on_lynch)

    target = lynch_mob.check_thresholds(crew, current_paranoia=10)
    assert target is None
    assert not lynch_events

    target = lynch_mob.check_thresholds(crew, current_paranoia=thresholds.lynch_paranoia_trigger)
    assert target is not None
    assert target.name == "Norris"
    assert lynch_events
    assert lynch_events[-1].payload["average_trust"] < thresholds.lynch_average_threshold

    event_bus.unsubscribe(EventType.LYNCH_MOB_TRIGGER, on_lynch)
