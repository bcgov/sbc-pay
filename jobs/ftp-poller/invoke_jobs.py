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
"""Generate account statements.

This module will create statement records for each account.
"""
import os
import sys

from flask import Flask
from pay_api.services.gcp_queue import queue

import config
from utils.logger import setup_logging

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), "logging.conf"))  # important to do this first


def create_app(run_mode=os.getenv("FLASK_ENV", "production")):
    """Return a configured Flask App using the Factory method."""
    from pay_api.models import db, ma

    app = Flask(__name__)

    app.config.from_object(config.CONFIGURATION[run_mode])

    app.logger.info("<<<< Starting Ftp Poller Job >>>>")
    queue.init_app(app)
    ma.init_app(app)

    register_shellcontext(app)

    return app


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {"app": app}  # pragma: no cover

    app.shell_context_processor(shell_context)


def run(job_name):
    from tasks.cas_poller_ftp import CASPollerFtpTask
    from tasks.cgi_feeder_poller_task import CGIFeederPollerTask
    from tasks.eft_poller_ftp import EFTPollerFtpTask
    from tasks.google_bucket_poller import GoogleBucketPollerTask

    application = create_app()

    application.app_context().push()
    match job_name:
        case "CAS_FTP_POLLER":
            CASPollerFtpTask.poll_ftp()
            application.logger.info("<<<< Completed Polling CAS FTP >>>>")
        case "CGI_FTP_POLLER":
            CGIFeederPollerTask.poll_ftp()
            application.logger.info("<<<< Completed Polling CGI FTP >>>>")
        case "EFT_FTP_POLLER":
            EFTPollerFtpTask.poll_ftp()
            application.logger.info("<<<< Completed Polling EFT FTP >>>>")
        case "GOOGLE_BUCKET_POLLER":
            GoogleBucketPollerTask.poll_google_bucket_for_ejv_files()
            application.logger.info("<<<< Completed Polling Google Buckets >>>>")
        case _:
            application.logger.debug("No valid args passed.Exiting job without running any ***************")


if __name__ == "__main__":
    print("----------------------------Scheduler Ran With Argument--", sys.argv[1])
    run(sys.argv[1])
