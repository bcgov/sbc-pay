"""Converter module to support decimal and datetime serialization."""

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import cattrs
from attrs import fields, has
from cattrs.gen import make_dict_structure_fn, make_dict_unstructure_fn, override


class CurrencyStr(str):
    """Formatted currency string type."""

    def __new__(cls, value):
        if value is None:
            value = "0.00"
        elif isinstance(value, (Decimal, int, float)):
            value = f"{value:.2f}"
        else:
            value = str(value)
        return str.__new__(cls, value)


class FullMonthDateStr(str):
    """Formatted date string type in '%B %d, %Y' format."""

    def __new__(cls, value):
        if value is None:
            return None
        if isinstance(value, datetime):
            value = value.strftime("%B %d, %Y")
        return str.__new__(cls, value)


class Converter(cattrs.Converter):
    """Addon to cattr converter."""

    def __init__(
        self,
        camel_to_snake_case: bool = False,
        snake_case_to_camel=False,
        enum_to_value: bool = False,
    ):
        """Initialize function, add in extra unstructure hooks."""
        super().__init__()
        # More from cattrs-extras/blob/master/src/cattrs_extras/converter.py
        self.register_structure_hook(Decimal, self._structure_decimal)
        self.register_unstructure_hook(Decimal, self._unstructure_decimal)
        self.register_unstructure_hook(datetime, self._unstructure_datetime)
        self.register_structure_hook(CurrencyStr, self.structure_formatted_currency)
        self.register_unstructure_hook(CurrencyStr, self._unstructure_formatted_currency)
        self.register_structure_hook(FullMonthDateStr, self.structure_month_date_year_str)
        self.register_unstructure_hook(FullMonthDateStr, self._unstructure_statement_date_str)
        # Note we may need a hook to handle str = None, sometimes a str set to None would become 'None'

        if enum_to_value:
            self.register_structure_hook(Enum, self._structure_enum_value)

        if camel_to_snake_case:
            self.register_unstructure_hook_factory(has, self._to_snake_case_unstructure)
            self.register_structure_hook_factory(has, self._to_snake_case_structure)

        if snake_case_to_camel:
            self.register_unstructure_hook_factory(has, self._to_camel_case_unstructure)
            self.register_structure_hook_factory(has, self._to_camel_case_structure)

    def _to_snake_case(self, camel_str: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", camel_str).lower()

    def _to_camel_case(self, snake_str: str) -> str:
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    def _to_camel_case_unstructure(self, cls):
        return make_dict_unstructure_fn(
            cls, self, **{a.name: override(rename=self._to_camel_case(a.name)) for a in fields(cls)}
        )

    def _to_camel_case_structure(self, cls):
        return make_dict_structure_fn(
            cls, self, **{a.name: override(rename=self._to_camel_case(a.name)) for a in fields(cls)}
        )

    def _to_snake_case_unstructure(self, cls):
        return make_dict_unstructure_fn(
            cls, self, **{a.name: override(rename=self._to_snake_case(a.name)) for a in fields(cls)}
        )

    def _to_snake_case_structure(self, cls):
        # When structuring the target classes attribute is used for look up on the source, so we need to convert it
        # to camel case.
        return make_dict_structure_fn(
            cls, self, **{a.name: override(rename=self._to_camel_case(a.name)) for a in fields(cls)}
        )

    @staticmethod
    def _structure_decimal(obj: Any, cls: type) -> Decimal:
        return cls(str(obj))

    @staticmethod
    def _structure_enum_value(obj: Any, cls: type):
        if not issubclass(cls, Enum):
            return None
        # Enum automatically comes in as the value here, just return it
        return obj

    @staticmethod
    def _unstructure_decimal(obj: Decimal) -> float:
        return float(obj or 0)

    @staticmethod
    def _unstructure_datetime(obj: datetime) -> str:
        return obj.isoformat() if obj else None

    @staticmethod
    def _structure_datetime():
        return lambda value, _: (datetime.fromisoformat(value) if isinstance(value, str) else value)

    @staticmethod
    def remove_nones(data: dict[Any, Any]) -> dict[str, Any]:
        """Remove nones from payload."""
        new_data = {}
        for key, val in data.items():
            if isinstance(val, dict):
                new_data[key] = Converter.remove_nones(val)
            elif isinstance(val, list):
                new_data[key] = [Converter.remove_nones(item) if isinstance(item, dict) else item for item in val]
            elif val is not None:
                new_data[key] = val
        return new_data

    @staticmethod
    def structure_formatted_currency(obj: Any) -> CurrencyStr:
        return CurrencyStr(obj)

    @staticmethod
    def _unstructure_formatted_currency(obj: CurrencyStr) -> str:
        """Convert CurrencyStr to formatted string."""
        try:
            return f"{float(obj):,.2f}"
        except (TypeError, ValueError):
            return "0.00"

    @staticmethod
    def structure_month_date_year_str(obj: Any) -> FullMonthDateStr | None:
        if obj is None:
            return None
        return FullMonthDateStr(obj)

    @staticmethod
    def _unstructure_statement_date_str(obj: FullMonthDateStr) -> str | None:
        """FullMonthDateStr is already a formatted string."""
        return obj if obj else None
