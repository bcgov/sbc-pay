import dataclasses
from enum import Enum
from typing import Any, Dict, List, Optional


class StatementNotificationAction(Enum):
    """Enum for the action to take for a statement."""

    DUE = "due"
    OVERDUE = "overdue"
    REMINDER = "reminder"
