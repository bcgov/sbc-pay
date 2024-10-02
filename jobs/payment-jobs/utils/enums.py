from enum import Enum


class StatementNotificationAction(Enum):
    """Enum for the action to take for a statement."""

    DUE = 'due'
    OVERDUE = 'overdue'
    REMINDER = 'reminder'
