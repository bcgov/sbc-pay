"""Iterates through each CFS record and populates the payment_method field based on the reciept method in CFS.

Note we may skip this one and manually run it in prod, as there is no more prehook.

Revision ID: 248cf4155e19
Revises: f6990cf5ddf1
Create Date: 2024-07-11 12:36:16.433028

"""
import aiohttp
import asyncio

import ctypes
from sql_versioning import versioned_session
from sqlalchemy import event

from sqlalchemy.orm import load_only
from flask import current_app
from typing import List 

from pay_api.models import db
from pay_api.models.cfs_account import CfsAccount as CfsAccountModel
from pay_api.services.cfs_service import CFSService
from pay_api.utils.enums import CfsAccountStatus, ContentType, PaymentMethod


# revision identifiers, used by Alembic.
revision = '248cf4155e19'
down_revision = 'f6990cf5ddf1'
branch_labels = None
depends_on = None

def remove_versioning():
    key = [k for k in event.registry._key_to_collection if k[1] == 'before_flush'][0]
    identifier = key[1]
    fn = ctypes.cast(key[2], ctypes.py_object).value  # get function by id
    event.remove(db.session, identifier, fn)

async def get_sites(cfs_accounts: List[CfsAccountModel]):
    current_app.logger.disabled = False
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
            site_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}/sites/{cfs_account.cfs_site}/'
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
                site = await task.json()
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
                current_app.logger.info(f'Updated CFS Account: {cfs_account.id} - {cfs_account_number} {cfs_party_number} {cfs_site_number} - {task.url} - {cfs_account.payment_method}')


        cfs_accounts = CfsAccountModel.query.filter(CfsAccountModel.status.in_([CfsAccountStatus.PENDING_PAD_ACTIVATION.value])).all()
        for cfs_account in cfs_accounts:
            cfs_account.payment_method = PaymentMethod.PAD.value
            cfs_account.flush()

        db.session.commit()

def upgrade():
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

def downgrade():
    pass
