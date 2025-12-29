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
"""Logger utility for console and file logging without StructuredLogHandler."""

import logging
import os
import sys
from datetime import datetime


class LoggerUtil:
    """Utility class for creating console and file loggers."""

    _loggers = {}

    @classmethod
    def _remove_structured_handlers(cls):
        """Remove StructuredLogHandler from all loggers globally."""
        for name in [None, "invoke_jobs", "api-exceptions"]:
            logger = logging.getLogger(name)
            logger.handlers = [
                h
                for h in logger.handlers
                if "StructuredLogHandler" not in str(type(h))
            ]

    @classmethod
    def _setup_logger(cls, logger, logger_key: str):
        """Configure logger with standard settings."""
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.propagate = False
        cls._loggers[logger_key] = logger
        return logger

    @classmethod
    def get_console_logger(cls, logger_name: str):
        """Get console logger without StructuredLogHandler."""
        if logger_name not in cls._loggers:
            cls._remove_structured_handlers()

            logger = logging.getLogger(logger_name)
            cls._setup_logger(logger, logger_name)

            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)

        return cls._loggers[logger_name]

    @classmethod
    def get_file_logger(cls, logger_name: str, log_file_path: str = None):
        """Get file logger without StructuredLogHandler.

        Args:
            logger_name: Name of the logger
            log_file_path: Path to the log file. If not provided,
                creates a file in logs/ directory.
        """
        if log_file_path is None:
            project_root = os.path.abspath(
                os.path.dirname(os.path.dirname(__file__))
            )
            logs_dir = os.path.join(project_root, "logs")
            os.makedirs(logs_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = os.path.join(logs_dir, f"{logger_name}_{timestamp}.log")

        logger_key = f"{logger_name}_file_{log_file_path}"
        if logger_key not in cls._loggers:
            cls._remove_structured_handlers()

            logger = logging.getLogger(logger_key)
            cls._setup_logger(logger, logger_key)

            handler = logging.FileHandler(log_file_path)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(message)s",
                    "%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(handler)

        return cls._loggers[logger_key]
