# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Base class for audit model."""
from datetime import datetime, timezone

from marshmallow import fields
from sqlalchemy.ext.declarative import declared_attr

from pay_api.utils.user_context import user_context
from .base_model import BaseModel
from .db import db


class Audit(BaseModel):  # pylint: disable=too-few-public-methods
    """This class provides base methods for Auditable Table."""

    __abstract__ = True

    created_on = db.Column(
        "created_on",
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )
    updated_on = db.Column(
        "updated_on",
        db.DateTime,
        default=None,
        onupdate=lambda: datetime.now(tz=timezone.utc),
    )

    @declared_attr
    def created_by(cls):  # pylint:disable=no-self-argument, # noqa: N805
        """Return created by."""
        return db.Column("created_by", db.String(50), nullable=False, default=cls._get_user_name)

    @declared_attr
    def created_name(cls):  # pylint:disable=no-self-argument, # noqa: N805
        """Return created name."""
        return db.Column("created_name", db.String(100), nullable=True, default=cls._get_name)

    @declared_attr
    def updated_by(cls):  # pylint:disable=no-self-argument, # noqa: N805
        """Return updated by."""
        return db.Column(
            "updated_by",
            db.String(50),
            nullable=True,
            default=None,
            onupdate=cls._get_user_name,
        )

    @declared_attr
    def updated_name(cls):  # pylint:disable=no-self-argument, # noqa: N805
        """Return updated by."""
        return db.Column(
            "updated_name",
            db.String(50),
            nullable=True,
            default=None,
            onupdate=cls._get_name,
        )

    @staticmethod
    @user_context
    def _get_user_name(**kwargs):
        """Return current user user_name."""
        return kwargs["user"].user_name

    @staticmethod
    @user_context
    def _get_name(**kwargs):
        """Return current user's name."""
        return kwargs["user"].name


class AuditSchema:  # pylint: disable=too-many-ancestors, too-few-public-methods
    """Audit Schema."""

    created_on = fields.DateTime()
    updated_on = fields.DateTime()
