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
"""Logger utility for console logging without StructuredLogHandler."""

import logging
import sys


class LoggerUtil:
    """Utility class for creating console loggers."""

    _loggers = {}

    @classmethod
    def get_console_logger(cls, logger_name: str):
        """Get console logger without StructuredLogHandler."""
        if logger_name not in cls._loggers:
            # Remove StructuredLogHandler from all loggers globally
            for name in [None, "invoke_jobs", "api-exceptions"]:
                logger = logging.getLogger(name)
                logger.handlers = [h for h in logger.handlers if "StructuredLogHandler" not in str(type(h))]

            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)
            logger.handlers.clear()
            logger.propagate = False

            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
            cls._loggers[logger_name] = logger

        return cls._loggers[logger_name]
