# Copyright © 2019 Province of British Columbia
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

from flask import current_app
from sqlalchemy_continuum.plugins.flask import fetch_remote_addr

from pay_api.utils.user_context import user_context
from .db import db, activity_plugin


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
        self.create_activity(self)
        return self

    def save(self):
        """Save and commit."""
        db.session.add(self)
        db.session.flush()
        self.create_activity(self)
        db.session.commit()
        return self

    @staticmethod
    def rollback():
        """RollBack."""
        db.session.rollback()

    @classmethod
    def find_by_id(cls, identifier: int):
        """Return model by id."""
        return cls.query.get(identifier)

    @classmethod
    def create_activity(cls, obj):
        """Create activity records if the model is versioned."""
        if isinstance(obj, VersionedModel) and not current_app.config.get('DISABLE_ACTIVITY_LOGS'):
            activity = activity_plugin.activity_cls(verb='update', object=obj, data={
                'user_name': cls._get_user_name(),
                'remote_addr': fetch_remote_addr()
            })

            db.session.add(activity)

    @staticmethod
    @user_context
    def _get_user_name(**kwargs):
        """Return current user user_name."""
        return kwargs['user'].user_name


class VersionedModel(BaseModel):
    """This class manages all of the base code, type or status model functions."""

    __abstract__ = True

    __versioned__ = {
        'exclude': []
    }
