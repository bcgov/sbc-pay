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
"""Update bank name for PAD accounts one time.

This module is a one time job to update the names.
"""
import os
import re
import sys
from typing import Dict, List

import sentry_sdk
from flask import Flask, current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db, ma
from pay_api.services.cfs_service import CFSService
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.constants import DEFAULT_COUNTRY, DEFAULT_CURRENCY
from pay_api.utils.enums import AuthHeaderType, ContentType, PaymentMethod
from sentry_sdk.integrations.flask import FlaskIntegration

import config
from utils.logger import setup_logging

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), "logging.conf"))  # important to do this first


def create_app(run_mode=os.getenv("FLASK_ENV", "production")):
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)

    app.config.from_object(config.CONFIGURATION[run_mode])
    # Configure Sentry
    if str(app.config.get("SENTRY_ENABLE")).lower() == "true":
        if app.config.get("SENTRY_DSN", None):
            sentry_sdk.init(dsn=app.config.get("SENTRY_DSN"), integrations=[FlaskIntegration()])
    db.init_app(app)
    ma.init_app(app)

    register_shellcontext(app)

    return app


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {"app": app}  # pragma: no cover

    app.shell_context_processor(shell_context)


def run_update(pay_account_id, num_records):
    """Update bank info."""
    current_app.logger.info(f"<<<< Running Update for account id from :{pay_account_id} and total:{num_records} >>>>")
    pad_accounts: List[PaymentAccountModel] = (
        db.session.query(PaymentAccountModel)
        .filter(PaymentAccountModel.payment_method == PaymentMethod.PAD.value)
        .filter(PaymentAccountModel.id >= pay_account_id)
        .order_by(PaymentAccountModel.id.asc())
        .limit(num_records)
        .all()
    )
    access_token: str = CFSService.get_token().json().get("access_token")
    current_app.logger.info(f"<<<< Total number of records founds: {len(pad_accounts)}")
    current_app.logger.info(f"<<<< records founds: {[accnt.id for accnt in pad_accounts]}")
    if len(pad_accounts) == 0:
        return

    for payment_account in pad_accounts:
        cfs_account = CfsAccountModel.find_effective_by_payment_method(payment_account.id, PaymentMethod.PAD.value)
        current_app.logger.info(
            f"<<<< Running Update for account id :{payment_account.id} and cfs_account:{cfs_account.id} >>>>"
        )
        # payment_details = get_bank_info(cfs_account.cfs_party, cfs_account.cfs_account, cfs_account.cfs_site)
        # current_app.logger.info(payment_details)

        name = re.sub(r"[^a-zA-Z0-9]+", " ", payment_account.name)

        payment_info: Dict[str, any] = {
            "bankInstitutionNumber": cfs_account.bank_number,
            "bankTransitNumber": cfs_account.bank_branch_number,
            "bankAccountNumber": cfs_account.bank_account_number,
            "bankAccountName": name,
        }

        save_bank_details(
            access_token,
            cfs_account.cfs_party,
            cfs_account.cfs_account,
            cfs_account.cfs_site,
            payment_info,
        )

        current_app.logger.info(
            f"<<<< Successfully Updated for account id :{payment_account.id} and cfs_account:{cfs_account.id} >>>>"
        )


def get_bank_info(
    party_number: str,  # pylint: disable=too-many-arguments
    account_number: str,
    site_number: str,
):
    """Get bank details to the site."""
    current_app.logger.debug("<Updating CFS payment details ")
    site_payment_url = (
        current_app.config.post("CFS_BASE_URL")
        + f"/cfs/parties/{party_number}/accs/{account_number}/sites/{site_number}/payment/"
    )
    access_token: str = CFSService.get_token().json().get("access_token")
    payment_details = CFSService.get(
        site_payment_url,
        access_token,
        AuthHeaderType.BEARER,
        ContentType.JSON,
        additional_headers={"Pay-Connector": current_app.config.get("PAY_CONNECTOR_AUTH")},
    )
    return payment_details.json()


def save_bank_details(
    access_token,
    party_number: str,  # pylint: disable=too-many-arguments
    account_number: str,
    site_number: str,
    payment_info: Dict[str, str],
):
    """Update bank details to the site."""
    current_app.logger.debug("<Creating CFS payment details ")
    site_payment_url = (
        current_app.config.get("CFS_BASE_URL")
        + f"/cfs/parties/{party_number}/accs/{account_number}/sites/{site_number}/payment/"
    )

    bank_number = str(payment_info.get("bankInstitutionNumber"))
    branch_number = str(payment_info.get("bankTransitNumber"))

    # bank account name should match legal name
    name = re.sub(r"[^a-zA-Z0-9]+", " ", payment_info.get("bankAccountName", ""))

    payment_details: Dict[str, str] = {
        "bank_account_name": name,
        "bank_number": f"{bank_number:0>4}",
        "branch_number": f"{branch_number:0>5}",
        "bank_account_number": str(payment_info.get("bankAccountNumber")),
        "country_code": DEFAULT_COUNTRY,
        "currency_code": DEFAULT_CURRENCY,
    }
    site_payment_response = OAuthService.post(
        site_payment_url,
        access_token,
        AuthHeaderType.BEARER,
        ContentType.JSON,
        payment_details,
        additional_headers={"Pay-Connector": current_app.config.get("PAY_CONNECTOR_AUTH")},
    ).json()
    current_app.logger.debug("<<<<<<")
    current_app.logger.debug(site_payment_response)
    current_app.logger.debug(">>>>>>")

    current_app.logger.debug(">Updated CFS payment details")
    return payment_details


if __name__ == "__main__":
    # first arg is account id to start with. Pay Account ID
    # second argument is how many records should it update.Just a stepper for reducing CFS load
    print("len:", len(sys.argv))
    if len(sys.argv) <= 2:
        print("No valid args passed.Exiting job without running any actions***************")
    COUNT = sys.argv[2] if len(sys.argv) == 3 else 10
    application = create_app()
    application.app_context().push()
    run_update(sys.argv[1], COUNT)
