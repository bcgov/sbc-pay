import dataclasses
from enum import Enum
from typing import Any, Dict, List, Optional


class StatementNotificationAction(Enum):
    """Enum for the action to take for a statement."""

    DUE = "due"
    OVERDUE = "overdue"
    REMINDER = "reminder"

@dataclasses.dataclass
class EmailParams:
    """Params required to send error email."""

    subject: Optional[str] = ""
    file_name: Optional[str] = None
    minio_location: Optional[str] = None
    error_messages: Optional[List[Dict[str, Any]]] = dataclasses.field(default_factory=list)
    table_name: Optional[str] = None
