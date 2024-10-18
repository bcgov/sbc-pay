"""Rationale behind creating these DTOS below.

1. To ensure that the request and response payloads are validated before they are passed to the service layer.
2. To ensure that the request and response payloads are consistent across the application.
3. To ensure that the request and response payloads are consistent with the API documentation.

In the near future, will find a library that generates our API spec based off of these DTOs.
"""

from decimal import Decimal
from typing import List

from attrs import define

from pay_api.utils.converter import Converter
from pay_api.utils.serializable import Serializable


@define
class EFTShortNameGetRequest(Serializable):
    """EFT Short name search."""

    short_name: str = None
    short_name_id: int = None
    short_name_type: str = None
    amount_owing: Decimal = None
    statement_id: int = None
    state: str = None
    page: int = 1
    limit: int = 10
    account_id: int = None
    account_name: str = None
    account_branch: str = None
    account_id_list: str = None

    @classmethod
    def from_dict(cls, data: dict):
        """Convert from request args to EFTShortNameSearchDTO."""
        dto = super().from_dict(data)
        # In the future, we'll need a cleaner way to handle this.
        dto.state = dto.state.split(",") if dto.state else None
        dto.account_id_list = dto.account_id_list.split(",") if dto.account_id_list else None
        return dto


@define
class EFTShortNameSummaryGetRequest(Serializable):
    """EFT Short name summary search."""

    short_name: str = None
    short_name_id: int = None
    short_name_type: str = None
    credits_remaining: Decimal = None
    linked_accounts_count: int = None
    payment_received_start_date: str = None
    payment_received_end_date: str = None
    page: int = 1
    limit: int = 10


@define
class EFTShortNameRefundPatchRequest(Serializable):
    """EFT Short name refund DTO."""

    comment: str
    status: str
    decline_reason: str = None


@define
class EFTShortNameRefundGetRequest():
    """EFT Short name refund DTO."""

    statuses: List[str]
    short_name_id: int = None

    @classmethod
    def from_dict(cls, data: dict):
        """Convert from request json to EFTShortNameRefundDTO."""
        converter = Converter()
        short_name_id = converter.convert_to_int(data.get("shortNameId"))
        input_string = data.get("statuses", "")
        statuses = input_string.split(",") if input_string else []
        return EFTShortNameRefundGetRequest(statuses=statuses, short_name_id=short_name_id)
