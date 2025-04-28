from typing import Optional

from attrs import define

from pay_api.utils.serializable import Serializable


@define
class ProductGetRequest(Serializable):
    """Retrieve product DTO."""

    product_code: Optional[str] = None