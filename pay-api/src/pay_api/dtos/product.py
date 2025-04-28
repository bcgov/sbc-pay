from typing import Optional

from attrs import define

from pay_api.utils.serializable import Serializable


@define
class ProductFeeGetRequest(Serializable):
    """Retrieve product fee DTO."""

    product_code: Optional[str] = None
