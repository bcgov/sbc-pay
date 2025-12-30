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
"""Super class to handle all operations related to base model."""

from decimal import Decimal
from typing import Self

from .db import db


class BaseModel(db.Model):
    """This class manages all of the base model functions."""

    __abstract__ = True

    @staticmethod
    def commit():
        """Commit the session."""
        db.session.commit()

    def flush(self):
        """Save and flush."""
        db.session.add(self)
        db.session.flush()
        return self

    def save_or_add(self, auto_save: bool):
        """Run save if auto save is True."""
        if auto_save:
            self.save()
        else:
            db.session.add(self)
        return self

    def save(self):
        """Save and commit."""
        db.session.add(self)
        db.session.commit()
        return self

    def delete(self):
        """Delete and commit."""
        db.session.delete(self)
        db.session.commit()

    def to_dict(self):
        """Quick and easy way to convert to a dict."""
        # We need a better way to do this in the future.
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if value is not None:
                if isinstance(value, int):
                    result[column.name] = value
                elif isinstance(value, Decimal | float):
                    result[column.name] = float(value)
                else:
                    result[column.name] = str(value)
        return result

    @staticmethod
    def rollback():
        """RollBack."""
        db.session.rollback()

    @classmethod
    def find_by_id(cls, identifier: int) -> Self:
        """Return model by id."""
        if identifier:
            return db.session.get(cls, identifier)
        return None

    @classmethod
    def find_by_id_for_update(cls, identifier: int) -> Self:
        """Return model by id with lock to avoid race conditions."""
        with db.session.begin():
            if identifier:
                return cls.query.filter_by(id=identifier).with_for_update().one_or_none()
            return None
