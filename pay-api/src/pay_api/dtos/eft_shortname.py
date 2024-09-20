"""Rationale behind creating these DTOS below.

1. To ensure that the request and response payloads are validated before they are passed to the service layer.
2. To ensure that the request and response payloads are consistent across the application.
3. To ensure that the request and response payloads are consistent with the API documentation.

In the near future, will find a library that generates our API spec based off of these DTOs.
"""
from decimal import Decimal
from attrs import define
from typing import List

from pay_api.utils.converter import Converter


@define
class EFTShortNameGetRequest:
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
        dto = Converter(camel_to_snake_case=True).structure(data, EFTShortNameGetRequest)
        # In the future, we'll need a cleaner way to handle this.
        dto.state = dto.state.split(',') if dto.state else None
        dto.account_id_list = dto.account_id_list.split(',') if dto.account_id_list else None
        return dto


@define
class EFTShortNameSummaryGetRequest:
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

    @classmethod
    def from_dict(cls, data: dict):
        """Convert from request args to EFTShortNameSummarySearchDTO."""
        dto = Converter(camel_to_snake_case=True).structure(data, EFTShortNameSummaryGetRequest)
        return dto


@define
class EFTShortNameRefundPatchRequest:
    """EFT Short name refund DTO."""

    comment: str
    declined_reason: str
    status: str

    @classmethod
    def from_dict(cls, data: dict):
        """Convert from request json to EFTShortNameRefundDTO."""
        return Converter(camel_to_snake_case=True).structure(data, EFTShortNameRefundPatchRequest)


@define
class EFTShortNameRefundGetRequest:
    """EFT Short name refund DTO."""

    statuses: List[str]

    @classmethod
    def from_dict(cls, data: dict):
        """Convert from request json to EFTShortNameRefundDTO."""
        EFTShortNameRefundGetRequest(statuses=data.get('status', []))
