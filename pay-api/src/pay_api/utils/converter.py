"""Converter module to support decimal and datetime serialization."""
import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Type
import cattrs
from attrs import fields, has
from cattrs.gen import make_dict_structure_fn, make_dict_unstructure_fn, override


class Converter(cattrs.Converter):
    """Addon to cattr converter."""

    def __init__(self, camel_to_snake_case: bool = False, snake_case_to_camel=False, enum_to_value: bool = False):
        """Initialize function, add in extra unstructure hooks."""
        super().__init__()
        # More from cattrs-extras/blob/master/src/cattrs_extras/converter.py
        self.register_structure_hook(Decimal, self._structure_decimal)
        self.register_unstructure_hook(Decimal, self._unstructure_decimal)
        self.register_unstructure_hook(datetime, self._unstructure_datetime)

        if enum_to_value:
            self.register_structure_hook(Enum, self._structure_enum_value)

        if camel_to_snake_case:
            self.register_unstructure_hook_factory(
                has, self._to_snake_case_unstructure
            )
            self.register_structure_hook_factory(
                has, self._to_snake_case_structure
            )

        if snake_case_to_camel:
            self.register_unstructure_hook_factory(
                has, self._to_camel_case_unstructure
            )

            self.register_structure_hook_factory(
                has, self._to_camel_case_structure
            )

    def _to_snake_case(self, camel_str: str) -> str:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()

    def _to_camel_case(self, snake_str: str) -> str:
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    def _to_camel_case_unstructure(self, cls):
        return make_dict_unstructure_fn(
            cls,
            self,
            **{
                a.name: override(rename=self._to_camel_case(a.name))
                for a in fields(cls)
            }
        )

    def _to_camel_case_structure(self, cls):
        return make_dict_structure_fn(
            cls,
            self,
            **{
                a.name: override(rename=self._to_camel_case(a.name))
                for a in fields(cls)
            }
        )

    def _to_snake_case_unstructure(self, cls):
        return make_dict_unstructure_fn(
            cls,
            self,
            **{
                a.name: override(rename=self._to_snake_case(a.name))
                for a in fields(cls)
            }
        )

    def _to_snake_case_structure(self, cls):
        # When structuring the target classes attribute is used for look up on the source, so we need to convert it
        # to camel case.
        return make_dict_structure_fn(
            cls,
            self,
            **{
                a.name: override(rename=self._to_camel_case(a.name))
                for a in fields(cls)
            }
        )

    @staticmethod
    def _structure_decimal(obj: Any, cls: Type) -> Decimal:
        return cls(str(obj))

    @staticmethod
    def _structure_enum_value(obj: Any, cls: Type):
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
    def remove_nones(data: Dict[Any, Any]) -> Dict[str, Any]:
        """Remove nones from payload."""
        new_data = {}
        for key, val in data.items():
            if isinstance(val, dict):
                new_data[key] = Converter.remove_nones(val)
            elif val is not None:
                new_data[key] = val
        return new_data
