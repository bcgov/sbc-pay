"""Rationale behind creating these DTOS below.

1. To ensure that the request and response payloads are validated before they are passed to the service layer.
2. To ensure that the request and response payloads are consistent across the application.
3. To ensure that the request and response payloads are consistent with the API documentation.

In the near future, will find a library that generates our API spec based off of these DTOs.
"""

from decimal import Decimal
from typing import Optional

from attrs import define
from cattrs import ClassValidationError

from pay_api.exceptions import BusinessException
from pay_api.utils.enums import APRefundMethod
from pay_api.utils.errors import Error
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

    status: Optional[str] = None
    comment: Optional[str] = None
    decline_reason: Optional[str] = None
    cheque_status: Optional[str] = None


@define
class EFTShortNameRefundPostRequest(Serializable):
    """EFT Short name refund DTO."""

    short_name_id: int
    refund_amount: Decimal
    refund_email: str
    refund_method: str
    comment: str
    cas_supplier_number: Optional[str] = None
    cas_supplier_site: Optional[str] = None
    entity_name: Optional[str] = None
    street: Optional[str] = None
    street_additional: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    delivery_instructions: Optional[str] = None

    def validate_for_refund_method(self):
        """Validate refund request - cheque needs mailing info, eft needs cas info."""

        def check_missing_fields(required_fields):
            return [field for field in required_fields if getattr(self, field, None) is None]

        invalid_request = check_missing_fields(["short_name_id", "refund_amount", "refund_email", "refund_method"])
        match self.refund_method:
            case APRefundMethod.EFT.value:
                invalid_request = check_missing_fields(["cas_supplier_number", "cas_supplier_site"])
            case APRefundMethod.CHEQUE.value:
                invalid_request = check_missing_fields(
                    ["entity_name", "street", "city", "region", "postal_code", "country"]
                )
            case _:
                invalid_request = True
        if self.refund_amount <= 0 or invalid_request:
            raise BusinessException(Error.INVALID_REFUND)

    @classmethod
    def from_dict(cls, data: dict):
        """Convert from request args to EFTShortNameSearchDTO."""
        try:
            dto = super().from_dict(data)
            return dto
        # This is for missing a required field.
        except ClassValidationError as cve:
            raise BusinessException(Error.INVALID_REQUEST) from cve


@define
class EFTShortNameRefundGetRequest(Serializable):
    """EFT Short name refund DTO."""

    statuses: str = None
    short_name_id: int = None

    @classmethod
    def from_dict(cls, data: dict):
        """Convert from request json to EFTShortNameRefundDTO."""
        dto = super().from_dict(data)
        dto.statuses = dto.statuses.split(",") if dto.statuses else []
        return dto
