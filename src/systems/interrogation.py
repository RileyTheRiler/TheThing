"""Interrogation and accusation dialogue system for The Thing game.

Allows players to question crew members and make formal accusations.
"""

from enum import Enum
from core.resolution import Attribute, Skill, ResolutionSystem
from core.event_system import event_bus, EventType, GameEvent


class InterrogationTopic(Enum):
    """Topics that can be asked about during interrogation."""
    WHEREABOUTS = "whereabouts"   # Where were you?
    ALIBI = "alibi"              # Who can vouch for you?
    SUSPICION = "suspicion"      # Who do you suspect?
    BEHAVIOR = "behavior"        # Why did you do X?
    KNOWLEDGE = "knowledge"      # What do you know about X?
    SCHEDULE_SLIP = "schedule_slip"  # Why are you off-schedule?


class ResponseType(Enum):
    """Types of responses during interrogation."""
    HONEST = "honest"
    EVASIVE = "evasive"
    DEFENSIVE = "defensive"
    ACCUSATORY = "accusatory"
    NERVOUS = "nervous"


class InterrogationResult:
    """Result of an interrogation attempt."""

    def __init__(self, response_type, dialogue, tells=None, trust_change=0,
                 out_of_schedule=False, schedule_message=None, schedule_reveal=None):
        self.response_type = response_type
        self.dialogue = dialogue
        self.tells = tells or []  # Behavioral tells that might indicate infection
        self.trust_change = trust_change
        self.out_of_schedule = out_of_schedule
        self.schedule_message = schedule_message
        self.schedule_reveal = schedule_reveal or {}


class AccusationResult:
    """Result of a formal accusation."""

    def __init__(self, supported, supporters, opposers, outcome_message):
        self.supported = supported  # Whether the mob supports the accusation
        self.supporters = supporters
        self.opposers = opposers
        self.outcome_message = outcome_message


class InterrogationSystem:
    """Handles interrogation dialogue and accusations."""

    # Bonus dice when interrogating NPCs who are out of their scheduled location
    WHEREABOUTS_BONUS = 2

    # Response templates for different topics and infection states
    RESPONSES = {
        InterrogationTopic.WHEREABOUTS: {
            True: [  # Infected responses
                ("I was... around. You know how it is.", ResponseType.EVASIVE),
                ("What does it matter where I was?", ResponseType.DEFENSIVE),
                ("I was in the {room}. Alone.", ResponseType.NERVOUS),
            ],
            False: [  # Human responses
                ("I was in the {room}, you saw me there.", ResponseType.HONEST),
                ("Check with {witness} - we were together.", ResponseType.HONEST),
                ("I don't remember exactly... it's been crazy.", ResponseType.NERVOUS),
            ]
        },
        InterrogationTopic.ALIBI: {
            True: [
                ("Nobody was with me. Is that a crime?", ResponseType.DEFENSIVE),
                ("{witness} saw me. Ask them.", ResponseType.EVASIVE),
                ("Why do I need an alibi? You're paranoid.", ResponseType.ACCUSATORY),
            ],
            False: [
                ("{witness} and I were working on repairs.", ResponseType.HONEST),
                ("I was with {witness} in the {room}.", ResponseType.HONEST),
                ("I think... maybe {witness} saw me?", ResponseType.NERVOUS),
            ]
        },
        InterrogationTopic.SUSPICION: {
            True: [
                ("I don't trust anyone anymore. Especially you.", ResponseType.ACCUSATORY),
                ("Maybe {target} isn't who they say they are.", ResponseType.EVASIVE),
                ("Everyone's acting strange. Hard to say.", ResponseType.EVASIVE),
            ],
            False: [
                ("Something's off about {target}. Watch them.", ResponseType.HONEST),
                ("I don't want to point fingers, but...", ResponseType.NERVOUS),
                ("We need to stick together, not accuse each other.", ResponseType.HONEST),
            ]
        },
        InterrogationTopic.BEHAVIOR: {
            True: [
                ("I don't have to explain myself to you!", ResponseType.DEFENSIVE),
                ("That's... not what happened.", ResponseType.EVASIVE),
                ("You're seeing things. The cold is getting to you.", ResponseType.ACCUSATORY),
            ],
            False: [
                ("I know it looked strange, but I can explain.", ResponseType.HONEST),
                ("I was scared. Weren't you?", ResponseType.NERVOUS),
                ("What would you have done in my place?", ResponseType.DEFENSIVE),
            ]
        },
        InterrogationTopic.KNOWLEDGE: {
            True: [
                ("I don't know anything. Leave me alone.", ResponseType.EVASIVE),
                ("Why are you asking me? Ask someone else.", ResponseType.DEFENSIVE),
                ("Knowledge is dangerous now, don't you think?", ResponseType.EVASIVE),
            ],
            False: [
                ("I heard something in the {room} last night.", ResponseType.HONEST),
                ("I saw {target} acting strange near the kennels.", ResponseType.HONEST),
                ("I wish I knew more. This is terrifying.", ResponseType.NERVOUS),
            ]
        },
        InterrogationTopic.SCHEDULE_SLIP: {
            True: [
                ("You're imagining things. I go where I'm needed.", ResponseType.DEFENSIVE),
                ("Someone must have messed with the schedule.", ResponseType.EVASIVE),
                ("Why does it matter? Everything's falling apart.", ResponseType.ACCUSATORY),
            ],
            False: [
                ("I... got lost. The corridors all look the same.", ResponseType.NERVOUS),
                ("I was helping elsewhere. Didn't anyone tell you?", ResponseType.DEFENSIVE),
                ("Sorry, I thought I was supposed to be in {room}.", ResponseType.HONEST),
            ]
        }
    }

    # Behavioral tells that suggest infection
    INFECTED_TELLS = [
        "Their eyes seem to flicker for a moment - a strange dilation.",
        "You notice their breath doesn't form vapor in the cold.",
        "Their movements seem slightly... off. Too fluid.",
        "They pause too long before responding.",
        "Their expression seems practiced, like a mask.",
        "You catch a faint, unfamiliar scent.",
        "Their shadow seems to move independently for a split second.",
    ]

    HUMAN_TELLS = [
        "They seem genuinely frightened.",
        "You see honest confusion in their eyes.",
        "Their hands are shaking from stress.",
        "They keep glancing at the exits nervously.",
        "Sweat beads on their forehead despite the cold.",
    ]

    def __init__(self, rng, room_states=None):
        self.rng = rng
        self.interrogation_count = {}  # name -> count (repeated interrogation raises suspicion)
        self.room_states = room_states

    def interrogate(self, interrogator, subject, topic, game_state):
        """Conduct an interrogation on a subject.

        Returns InterrogationResult with the subject's response and any tells.
        """
        schedule_reveal = None
        # Track interrogation count
        if subject.name not in self.interrogation_count:
            self.interrogation_count[subject.name] = 0
        self.interrogation_count[subject.name] += 1

        # Check if subject is out of schedule (provides interrogation bonus)
        out_of_schedule = False
        schedule_bonus = 0
        schedule_info = None
        if hasattr(subject, 'is_out_of_schedule'):
            out_of_schedule = subject.is_out_of_schedule(game_state)
            if out_of_schedule:
                schedule_bonus = self.WHEREABOUTS_BONUS
                schedule_info = subject.get_schedule_info(game_state)

        # Get possible responses based on infection status
        is_infected = subject.is_infected
        responses = self.RESPONSES.get(topic, self.RESPONSES[InterrogationTopic.WHEREABOUTS])
        possible = responses.get(is_infected, responses[False])

        # Knowledge Tags Injection (Agent 3)
        # If infected, check if we have a tag that provides a "perfect" cover
        injected_response = None
        if is_infected and hasattr(subject, 'knowledge_tags') and subject.knowledge_tags:
            if topic == InterrogationTopic.KNOWLEDGE:
                # Look for Protocol tags
                protocol_tags = [t for t in subject.knowledge_tags if "Protocol" in t]
                if protocol_tags:
                    tag = self.rng.choose(protocol_tags)
                    role = tag.split(": ")[1]
                    injected_response = (f"I'm strictly following {role} protocols. I know exactly what I'm doing.", ResponseType.HONEST)

            elif topic == InterrogationTopic.WHEREABOUTS:
                # Look for Memory tags
                memory_tags = [t for t in subject.knowledge_tags if "Memory" in t]
                if memory_tags:
                    tag = self.rng.choose(memory_tags)
                    interaction = tag.split(": ")[1]
                    injected_response = (f"I was occupied. I remember the {interaction} clearly.", ResponseType.HONEST)

        # Select a response
        if injected_response and self.rng.random_float() < 0.5:
            template, response_type = injected_response
        else:
            template, response_type = self.rng.choose(possible)

        # Fill in template variables
        other_crew = [m for m in game_state.crew if m != subject and m.is_alive]
        witness = self.rng.choose(other_crew).name if other_crew else "someone"
        target = self.rng.choose([m for m in other_crew if m != interrogator]).name if len(other_crew) > 1 else "someone"
        room = self.rng.choose(list(game_state.station_map.rooms.keys()))

        dialogue = template.format(witness=witness, target=target, room=room)

        # Determine if any tells are visible
        tells = []

        # Get room modifiers for empathy check
        room_modifiers = None
        current_room_states = getattr(game_state, 'room_states', self.room_states)
        if current_room_states:
            room_name = getattr(game_state.station_map, 'get_room_name', lambda *args: "Unknown")(*subject.location)
            if room_name != "Unknown":
                room_modifiers = current_room_states.get_resolution_modifiers(room_name)

        # Roll EMPATHY check to notice tells
        empathy_pool = (interrogator.attributes.get(Attribute.INFLUENCE, 1) +
                       interrogator.skills.get(Skill.EMPATHY, 0))

        # Apply schedule disruption bonus (target is out of expected location)
        if schedule_bonus > 0:
            empathy_pool += schedule_bonus

        # Apply environmental modifiers to empathy check
        if room_modifiers:
             # Use ResolutionSystem to apply the modifier if available or manual fallback
             from core.resolution import ResolutionSystem
             # If ResolutionSystem.adjust_pool exists, use it, otherwise assume modifiers are compatible
             if hasattr(ResolutionSystem, "adjust_pool"):
                  empathy_pool = ResolutionSystem.adjust_pool(empathy_pool, room_modifiers.observation_pool)
             else:
                  # Fallback: manually adjust
                  empathy_pool += room_modifiers.observation_pool

        check = self.rng.calculate_success(empathy_pool)

        if check['success']:
            # Successful empathy check - might notice a tell
            if is_infected:
                # Higher chance to notice infected tells
                if self.rng.random_float() < 0.4 + (self.interrogation_count[subject.name] * 0.1):
                    tells.append(self.rng.choose(self.INFECTED_TELLS))

                # Mask integrity affects visibility
                if subject.mask_integrity < 70 and self.rng.random_float() < 0.3:
                    tells.append(self.rng.choose(self.INFECTED_TELLS))
            else:
                # Can still notice human stress responses
                if self.rng.random_float() < 0.5:
                    tells.append(self.rng.choose(self.HUMAN_TELLS))

            # Successful read while subject is off-schedule reveals schedule/movements
            if out_of_schedule:
                schedule_reveal = {
                    "schedule": getattr(subject, "schedule", []),
                    "expected_room": schedule_info.get("expected_room") if schedule_info else None,
                    "current_room": schedule_info.get("current_room") if schedule_info else None,
                    "movement_history": list(getattr(subject, "movement_history", []))
                }
                schedule_text = self._format_schedule(getattr(subject, "schedule", []))
                movement_text = self._format_movement_history(getattr(subject, "movement_history", []))
                if schedule_text:
                    tells.append(f"Schedule: {schedule_text}")
                if movement_text:
                    tells.append(f"Recent movement: {movement_text}")

        # Calculate trust change
        trust_change = 0
        if response_type == ResponseType.DEFENSIVE:
            trust_change = -5
        elif response_type == ResponseType.ACCUSATORY:
            trust_change = -10
        elif response_type == ResponseType.EVASIVE:
            trust_change = -3
        elif response_type == ResponseType.HONEST:
            trust_change = 2

        # Repeated interrogation makes subject less cooperative
        if self.interrogation_count[subject.name] > 2:
            trust_change -= 5
            dialogue = f"(Annoyed) Again? Fine... {dialogue}"

        # Add schedule disruption message if applicable
        schedule_message = None
        if out_of_schedule and schedule_info:
            expected = schedule_info.get("expected_room", "Unknown")
            current = schedule_info.get("current_room", "Unknown")
            schedule_message = f"[!] {subject.name} should be in {expected}, but is in {current}. (+{schedule_bonus} to your check)"
            # Being out of schedule is inherently suspicious - small extra trust penalty
            if is_infected:
                trust_change -= 2

        result = InterrogationResult(
            response_type=response_type,
            dialogue=dialogue,
            tells=tells,
            trust_change=trust_change,
            out_of_schedule=out_of_schedule,
            schedule_message=schedule_message,
            schedule_reveal=schedule_reveal
        )

        # Emit event for UI/message reporter
        event_bus.emit(GameEvent(EventType.INTERROGATION_RESULT, {
            "interrogator": interrogator.name,
            "subject": subject.name,
            "topic": topic.value,
            "dialogue": dialogue,
            "response_type": response_type.value,
            "tells": tells,
            "trust_change": trust_change,
            "out_of_schedule": out_of_schedule,
            "schedule_message": schedule_message,
            "schedule_reveal": schedule_reveal
        }))

        return result

    def make_accusation(self, accuser, accused, evidence, game_state):
        """Make a formal accusation against a crew member.

        This can trigger a lynch mob vote.
        Returns AccusationResult with the outcome.
        """
        # Gather crew for vote
        voters = [m for m in game_state.crew
                 if m.is_alive and m != accuser and m != accused]

        if not voters:
            return AccusationResult(
                supported=False,
                supporters=[],
                opposers=[],
                outcome_message="There's no one else to support your accusation."
            )

        supporters = []
        opposers = []

        for voter in voters:
            # Base vote influenced by trust
            trust_in_accuser = game_state.trust_system.get_trust(voter.name, accuser.name)
            trust_in_accused = game_state.trust_system.get_trust(voter.name, accused.name)

            # Calculate vote probability
            vote_prob = 0.5

            # Trust difference matters
            trust_diff = trust_in_accuser - trust_in_accused
            vote_prob += trust_diff / 200  # -0.25 to +0.25 modifier

            # Evidence strength
            evidence_modifier = len(evidence) * 0.1  # Each piece of evidence adds 10%
            vote_prob += evidence_modifier

            # Infected voters might vote strategically
            if voter.is_infected:
                if accused.is_infected:
                    # Protect fellow infected
                    vote_prob -= 0.3
                else:
                    # Frame innocent humans
                    vote_prob += 0.2

            # Roll the vote
            if self.rng.random_float() < vote_prob:
                supporters.append(voter)
            else:
                opposers.append(voter)

        # Determine outcome
        supported = len(supporters) > len(opposers)

        if supported:
            outcome = f"The crew votes {len(supporters)}-{len(opposers)} to support your accusation!"
            # Emit lynch mob event
            event_bus.emit(GameEvent(EventType.LYNCH_MOB_VOTE, {
                "accuser": accuser.name,
                "accused": accused.name,
                "supporters": [s.name for s in supporters],
                "opposers": [o.name for o in opposers],
                "game_state": game_state
            }))
        else:
            outcome = f"The crew votes {len(opposers)}-{len(supporters)} against your accusation."
            # Failed accusation damages trust
            game_state.trust_system.modify_trust(accused.name, accuser.name, -20)
            for voter in voters:
                game_state.trust_system.modify_trust(voter.name, accuser.name, -5)

        # Emit reporting event
        event_bus.emit(GameEvent(EventType.ACCUSATION_RESULT, {
            "target": accused.name,
            "outcome": outcome,
            "supporters": [s.name for s in supporters],
            "opposers": [o.name for o in opposers],
            "supported": supported
        }))

        return AccusationResult(
            supported=supported,
            supporters=supporters,
            opposers=opposers,
            outcome_message=outcome
        )

    def confront_schedule_slip(self, interrogator, subject, game_state):
        """Special confrontation unlocked when a schedule slip is detected."""
        if not getattr(subject, "schedule_slip_flag", False):
            return InterrogationResult(
                response_type=ResponseType.EVASIVE,
                dialogue=f"{subject.name} looks confused. 'I'm on task, what's the problem?'",
                tells=[],
                trust_change=0
            )

        # Boosted empathy pool when you have concrete slip evidence
        empathy_pool = (interrogator.attributes.get(Attribute.INFLUENCE, 1) +
                        interrogator.skills.get(Skill.EMPATHY, 0) + 2)
        check = self.rng.calculate_success(max(0, empathy_pool))

        # Use slip reason as the confrontation opener
        slip_reason = getattr(subject, "schedule_slip_reason", "You weren't where you were supposed to be.")
        dialogue = f"You confront {subject.name}: {slip_reason}"

        tells = [slip_reason]
        trust_change = -5  # Baseline distrust from being called out

        # Successful pressure yields bigger tells and suspicion shifts
        if check["success"] or self.rng.random_float() < 0.35:
            extra_tell = self.rng.choose(self.INFECTED_TELLS if subject.is_infected else self.HUMAN_TELLS)
            if extra_tell:
                tells.append(extra_tell)
            trust_change -= 5  # Greater fallout when you catch them
            # Tilt trust in player's perception of the subject
            if hasattr(game_state, "trust_system"):
                game_state.trust_system.modify_trust(interrogator.name, subject.name, -10)
            # Amplify global suspicion slightly
            game_state.paranoia_level = min(100, game_state.paranoia_level + 1)
            dialogue += " They freeze under questioning."
        else:
            dialogue += " They deflect, but you make your concerns clear."

        # Clear the slip so it can't be exploited repeatedly in one loop
        subject.schedule_slip_flag = False

        result = InterrogationResult(
            response_type=ResponseType.DEFENSIVE if subject.is_infected else ResponseType.NERVOUS,
            dialogue=dialogue,
            tells=tells,
            trust_change=trust_change
        )

        event_bus.emit(GameEvent(EventType.INTERROGATION_RESULT, {
            "interrogator": interrogator.name,
            "subject": subject.name,
            "topic": InterrogationTopic.SCHEDULE_SLIP.value,
            "dialogue": dialogue,
            "response_type": result.response_type.value,
            "tells": tells,
            "trust_change": trust_change,
            "slip_detected": True
        }))

        return result

    def get_interrogation_topics(self):
        """Return available interrogation topics."""
        return list(InterrogationTopic)

    def _format_schedule(self, schedule):
        """Return a concise human-readable schedule string."""
        if not schedule:
            return ""
        parts = []
        for entry in schedule:
            start = entry.get("start")
            end = entry.get("end")
            room = entry.get("room", "Unknown")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                parts.append(room)
            else:
                parts.append(f"{int(start):02d}-{int(end):02d} {room}")
        return "; ".join(parts)

    def _format_movement_history(self, history):
        """Summarize the last few movement entries."""
        if not history:
            return ""
        recent = history[-3:]
        return ", ".join(
            f"T{entry.get('turn', '?')}: {entry.get('room', 'Unknown')}"
            for entry in recent
        )
