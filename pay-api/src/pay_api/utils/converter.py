"""Converter module to support decimal and datetime serialization."""
from decimal import Decimal
from datetime import datetime
import cattrs


class Converter(cattrs.Converter):
    """Addon to cattr converter."""

    def __init__(self):
        """Initialize function, add in extra unstructure hooks."""
        super().__init__()
        # More from cattrs-extras/blob/master/src/cattrs_extras/converter.py
        self.register_unstructure_hook(Decimal, self._unstructure_decimal)
        self.register_unstructure_hook(datetime, self._unstructure_datetime)

    @staticmethod
    def _unstructure_decimal(obj: Decimal) -> float:
        return float(obj or 0)

    @staticmethod
    def _unstructure_datetime(obj: datetime) -> str:
        return obj.isoformat()
