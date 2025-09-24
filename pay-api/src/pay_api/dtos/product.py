"""Rationale behind creating these DTOS below.

1. To ensure that the request and response payloads are validated before they are passed to the service layer.
2. To ensure that the request and response payloads are consistent across the application.
3. To ensure that the request and response payloads are consistent with the API documentation.

In the near future, will find a library that generates our API spec based off of these DTOs.
"""

from attrs import define

from pay_api.utils.serializable import Serializable


@define
class ProductFeeGetRequest(Serializable):
    """Retrieve product fee DTO."""

    product_code: str | None = None
