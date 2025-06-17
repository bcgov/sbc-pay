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

"""Tests to assure the logging utilities.

Test-Suite to ensure that the logging setup is working as expected.
"""

import json
import logging.config
import os

from pay_api.utils.logging import setup_logging


def test_logging_with_file(capsys):
    """Assert that logging is setup with the configuration file."""
    file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "logging.conf")
    setup_logging(file_path)  # important to do this first

    captured = capsys.readouterr()

    assert captured.out.startswith("Configure logging, from conf")


def test_logging_with_missing_file(capsys):
    """Assert that a message is sent to STDERR when the configuration doesn't exist."""
    file_path = None
    setup_logging(file_path)  # important to do this first

    captured = capsys.readouterr()

    assert captured.err.startswith("Unable to configure logging")


def test_logging_with_override_config(capsys):
    """Assert that logging is setup with the configuration from LOGGING_OVERRIDE_CONFIG environment variable."""
    test_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            }
        },
        "root": {"level": "INFO", "handlers": ["console"]},
    }

    os.environ["LOGGING_OVERRIDE_CONFIG"] = json.dumps(test_config)

    try:
        setup_logging(None, os.environ["LOGGING_OVERRIDE_CONFIG"])

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0

        test_logger = logging.getLogger("test_logger")
        test_logger.info("Test message")

        captured = capsys.readouterr()
        assert "Test message" in captured.out
    finally:
        del os.environ["LOGGING_OVERRIDE_CONFIG"]
        logging.config.dictConfig({"version": 1, "disable_existing_loggers": True})
