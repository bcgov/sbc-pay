"""Utility functions for testing."""

from datetime import datetime

import pytz

# Fit between CAS hours of operation.
valid_time_for_job = datetime.now(pytz.timezone("America/Vancouver")).replace(hour=12)
invalid_time_for_job = datetime.now(pytz.timezone("America/Vancouver")).replace(hour=1)
