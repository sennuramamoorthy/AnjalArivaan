"""
MockRuleEngine — canned-verdict rule engine used by unit tests.

Tests construct it with either a fixed decision (``decision=``) or a callable
(``decider=``) so each test can script the verdict for an incoming event.

Keeps a record of evaluated events for assertions.
"""

from typing import Callable, List, Optional

from src.modules.notification.domain.events import NewMailEvent
from src.modules.notification.rules.urgency_decision import UrgencyDecision
from src.modules.notification.domain.urgency_result import UrgencyLevel


class MockRuleEngine:
    def __init__(
        self,
        decision: Optional[UrgencyDecision] = None,
        decider: Optional[Callable[[NewMailEvent], UrgencyDecision]] = None,
    ) -> None:
        self._decision = decision
        self._decider = decider
        self.evaluated: List[NewMailEvent] = []

    def evaluate(self, event: NewMailEvent) -> UrgencyDecision:
        self.evaluated.append(event)
        if self._decider is not None:
            return self._decider(event)
        if self._decision is not None:
            return self._decision
        return UrgencyDecision(level=UrgencyLevel.NONE, reason="", matched_rule=None)
