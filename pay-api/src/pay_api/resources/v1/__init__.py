# Copyright © 2023 Province of British Columbia
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
"""Exposes all of the resource endpoints mounted in Flask-Blueprints."""

from typing import Optional

from flask import Flask  # noqa: TC002

from ..ops import bp as ops_bp  # noqa: TID252
from .account import bp as account_bp
from .account_statements import bp as account_statements_bp
from .account_statements_notifications import bp as account_notifications_bp
from .account_statements_settings import bp as account_settings_bp
from .bank_accounts import bp as bank_accounts_bp
from .code import bp as code_bp
from .distributions import bp as distributions_bp
from .documents import bp as documents_bp
from .eft_short_names import bp as eft_short_names_bp
from .fas import fas_refund_bp, fas_routing_slip_bp
from .fee import bp as fee_bp
from .fee_schedule import bp as fee_schedule_bp
from .invoice import bp as invoice_bp
from .invoice_receipt import bp as invoice_receipt_bp
from .invoices import bp as invoices_bp
from .meta import bp as meta_bp
from .non_sufficient_funds import bp as non_sufficient_funds_bp
from .payment import bp as payment_bp
from .refund import bp as refund_bp
from .transaction import bp as transaction_bp


class V1Endpoint:  # pylint: disable=too-few-public-methods,
    """Setup all the V1 Endpoints."""

    def __init__(self):
        """Create the endpoint setup, without initializations."""
        self.app: Flask | None = None

    def init_app(self, app):
        """Register and initialize the Endpoint setup."""
        if not app:
            raise Exception("Cannot initialize without a Flask App.")  # pylint: disable=broad-exception-raised

        self.app = app
        self.app.register_blueprint(account_bp)
        self.app.register_blueprint(account_notifications_bp)
        self.app.register_blueprint(account_settings_bp)
        self.app.register_blueprint(account_statements_bp)
        self.app.register_blueprint(bank_accounts_bp)
        self.app.register_blueprint(code_bp)
        self.app.register_blueprint(distributions_bp)
        self.app.register_blueprint(documents_bp)
        self.app.register_blueprint(eft_short_names_bp)
        self.app.register_blueprint(fas_refund_bp)
        self.app.register_blueprint(fas_routing_slip_bp)
        self.app.register_blueprint(fee_bp)
        self.app.register_blueprint(fee_schedule_bp)
        self.app.register_blueprint(invoice_bp)
        self.app.register_blueprint(invoices_bp)
        self.app.register_blueprint(invoice_receipt_bp)
        self.app.register_blueprint(meta_bp)
        self.app.register_blueprint(non_sufficient_funds_bp)
        self.app.register_blueprint(ops_bp)
        self.app.register_blueprint(payment_bp)
        self.app.register_blueprint(refund_bp)
        self.app.register_blueprint(transaction_bp)


v1_endpoint = V1Endpoint()
