"""Rationale behind creating these DTOS below.

1. To ensure that the request and response payloads are validated before they are passed to the service layer.
2. To ensure that the request and response payloads are consistent across the application.
3. To ensure that the request and response payloads are consistent with the API documentation.

In the near future, will find a library that generates our API spec based off of these DTOs.
"""

from decimal import Decimal

from attrs import define

from pay_api.utils.serializable import Serializable


@define
class RefundPatchRequest(Serializable):
    """Refund patch status DTO."""

    status: str | None = None
    decline_reason: str | None = None


@define
class RefundRequestGetRequest(Serializable):
    """Refund search."""

    invoice_id: int = None
    refund_status: str = None
    requested_by: str = None
    requested_start_date: str = None
    requested_end_date: str = None
    refund_reason: str = None
    transaction_amount: Decimal = None
    refund_amount: Decimal = None
    payment_method: str = None
    refund_method: str = None
    page: int = 1
    limit: int = 10
