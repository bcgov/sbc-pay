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
"""Centralized setup of logging for the service."""
import json
import logging
import logging.config
import sys
from os import path

from structured_logging import StructuredLogging


def setup_logging(conf, logging_override_content=None):
    """Create the services logger."""
    if logging_override_content:
        logging.config.dictConfig(json.loads(logging_override_content))
        print("Configure logging, from environment variable", file=sys.stdout)
    elif conf and path.isfile(conf):
        with open(conf, "r") as f:
            config = json.load(f)
        logging.config.dictConfig(config)
        print(f"Configure logging, from file:{conf}", file=sys.stdout)
    else:
        print(f"Unable to configure logging, attempted conf:{conf}", file=sys.stderr)


class StructuredLogHandler(logging.Handler):
    """StructuredLogHandler that wraps StructuredLogging."""

    def __init__(self, structured_logger=None):
        """Initialize the StructuredLogHandler."""
        super().__init__()
        self.structured_logger = structured_logger or StructuredLogging.get_logger()

    def emit(self, record):
        """Emit a record."""
        msg = self.format(record)
        level = record.levelname.lower()

        if level == "debug":
            self.structured_logger.debug(msg)
        elif level == "info":
            self.structured_logger.info(msg)
        elif level == "warning":
            self.structured_logger.warning(msg)
        elif level == "error":
            self.structured_logger.error(msg)
        elif level == "critical":
            self.structured_logger.critical(msg)
