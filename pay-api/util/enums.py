from enum import Enum


class AuthHeaderType(Enum):
    BASIC = 'Basic {}'
    BEARER = 'Bearer {}'


class ContentType(Enum):
    JSON = 'application/json'
    FORM_URL_ENCODED = 'application/x-www-form-urlencoded'
