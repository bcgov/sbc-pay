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
import ctypes

import asyncio
from typing import List
import aiohttp


from sqlalchemy import event
from sqlalchemy.orm import load_only

from sql_versioning import versioned_session

from flask import Flask, current_app

from pay_api.models import db, ma
from pay_api.models.cfs_account import CfsAccount as CfsAccountModel
from pay_api.services.cfs_service import CFSService
from pay_api.utils.enums import CfsAccountStatus, ContentType, PaymentMethod

import sentry_sdk

from sentry_sdk.integrations.flask import FlaskIntegration

import config
from utils.logger import setup_logging

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first


def create_app(run_mode=os.getenv('FLASK_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)

    app.config.from_object(config.CONFIGURATION[run_mode])
    # Configure Sentry
    if str(app.config.get('SENTRY_ENABLE')).lower() == 'true':
        if app.config.get('SENTRY_DSN', None):
            sentry_sdk.init(
                dsn=app.config.get('SENTRY_DSN'),
                integrations=[FlaskIntegration()]
            )
    db.init_app(app)
    ma.init_app(app)

    register_shellcontext(app)

    return app


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {
            'app': app
        }  # pragma: no cover

    app.shell_context_processor(shell_context)


def remove_versioning():
    """Remove the versioning, so the number doesn't update when we update rows."""
    # pylint: disable=protected-access
    key = [k for k in event.registry._key_to_collection
           if k[1] == 'before_flush'][0]
    identifier = key[1]
    fn = ctypes.cast(key[2], ctypes.py_object).value  # get function by id
    event.remove(db.session, identifier, fn)


def handle_site(task, json):
    """Handle the site response."""
    site = json
    cfs_payment_method = None
    match site.get('receipt_method'):
        case 'BCR-PAD Daily' | 'BCR-PAD Stop':
            cfs_payment_method = PaymentMethod.PAD.value
        case None:
            if site.get('customer_profile_class') == 'FAS_CORP_PROFILE':
                cfs_payment_method = PaymentMethod.INTERNAL.value
            else:
                cfs_payment_method = PaymentMethod.ONLINE_BANKING.value
        case _:
            current_app.logger.error(f'Invalid Payment System: {site.get("receipt_method")}')
    cfs_account_number = site.get('account_number')
    cfs_party_number = site.get('party_number')
    cfs_site_number = site.get('site_number')
    cfs_accounts = CfsAccountModel.query.filter(CfsAccountModel.cfs_account == cfs_account_number,
                                                CfsAccountModel.cfs_party == cfs_party_number,
                                                CfsAccountModel.cfs_site == cfs_site_number).all()
    for cfs_account in cfs_accounts:
        cfs_account.payment_method = cfs_payment_method
        cfs_account.flush()
    current_app.logger.info(f'Updated CFS Account: {cfs_account_number}'
                            f' {cfs_party_number} {cfs_site_number} - {task.url} -'
                            f' {cfs_payment_method}')


async def get_sites(cfs_accounts: List[CfsAccountModel]):
    """Get sites for the cfs_accounts and update the payment method."""
    current_app.logger.info('Updating CFS account rows with payment method by fetching from CAS. This requires VPN.')
    current_app.logger.info('Getting access token.')
    try:
        access_token = CFSService.get_token().json().get('access_token')
    except Exception as e:  # NOQA pylint:disable=broad-except
        current_app.logger.error(f'Error getting access token: {e} - Will need CFS_ACCOUNT.payment_method manually.')
        return

    connector = aiohttp.TCPConnector(limit=50)
    headers = {
        'Content-Type': ContentType.JSON.value,
        'Authorization': f'Bearer {access_token}'
    }
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        current_app.logger.info(f'Getting sites for {len(cfs_accounts)} accounts')
        for cfs_account in cfs_accounts:
            cfs_base: str = current_app.config.get('CFS_BASE_URL')
            site_url = f'{
                cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}/sites/{cfs_account.cfs_site}/'
            current_app.logger.info(f'Getting site: {site_url}')
            tasks.append(asyncio.create_task(session.get(site_url, headers=headers, timeout=2000)))
        tasks = await asyncio.gather(*tasks, return_exceptions=True)
        for task in tasks:
            if isinstance(task, aiohttp.ClientConnectionError):
                current_app.logger.error(f'{task.url} - Connection error')
            elif isinstance(task, asyncio.TimeoutError):
                current_app.logger.error(f'{task} - Timeout error')
            elif isinstance(task, aiohttp.ClientResponseError):
                current_app.logger.error(f'{task.request_info.real_url}- Exception: {task.status}')
            elif isinstance(task, Exception):
                current_app.logger.error(f'{task.url}- Exception: {task}')
            elif task.status != 200:
                current_app.logger.error(f'{task.url} - Returned non 200: {task.method} - {task.url} - {task.status}')
            else:
                handle_site(task, await task.json())

        cfs_accounts = CfsAccountModel.query.filter(CfsAccountModel.status.in_(
            [CfsAccountStatus.PENDING_PAD_ACTIVATION.value])).all()
        for cfs_account in cfs_accounts:
            cfs_account.payment_method = PaymentMethod.PAD.value
            cfs_account.flush()

        db.session.commit()


def run_update():
    """Update cfs_account.payment_method."""
    remove_versioning()
    cfs_accounts = CfsAccountModel.query.options(
                load_only(CfsAccountModel.cfs_account,
                          CfsAccountModel.cfs_party,
                          CfsAccountModel.cfs_account,
                          CfsAccountModel.cfs_site,
                          CfsAccountModel.payment_method
                          )).filter(CfsAccountModel.cfs_account.is_not(None), CfsAccountModel.payment_method.is_(None)).all()
    asyncio.run(get_sites(cfs_accounts))
    versioned_session(db.session)
    current_app.logger.info('Restoring versioned session.')


if __name__ == '__main__':
    application = create_app()
    application.app_context().push()
    run_update()
