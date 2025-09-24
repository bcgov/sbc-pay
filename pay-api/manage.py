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

"""Manage the database and some other items required to run the API."""

import logging

from flask_migrate import Migrate

# models included so that migrate can build the database migrations
from pay_api import (
    create_app,  # pylint: disable=unused-import
)
from pay_api.models import db

APP = create_app(run_mode="migration")
MIGRATE = Migrate(APP, db)

if __name__ == "__main__":
    logging.log(logging.INFO, "Running the Manager")
