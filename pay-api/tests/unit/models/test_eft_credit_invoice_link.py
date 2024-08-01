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

"""Tests to assure the EFT Credit invoice link model.

Test-Suite to ensure that the EFT Credit invoice link model is working as expected.
"""

from pay_api.models import EFTCredit, EFTCreditInvoiceLink, EFTFile, EFTShortnames, EFTTransaction
from pay_api.utils.enums import EFTCreditInvoiceStatus, EFTFileLineType, EFTProcessStatus, EFTShortnameStatus
from tests.utilities.base_test import factory_invoice, factory_payment_account


def test_eft_credit_invoice_link(session):
    """Assert eft credit invoice links are stored."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice = factory_invoice(payment_account=payment_account)
    invoice.save()

    assert payment_account.id is not None

    eft_short_name = EFTShortnames()
    eft_short_name.auth_account_id = payment_account.auth_account_id
    eft_short_name.status_code = EFTShortnameStatus.LINKED.value
    eft_short_name.short_name = 'TESTSHORTNAME'
    eft_short_name.save()

    eft_file = EFTFile()
    eft_file.file_ref = 'test.txt'
    eft_file.save()

    eft_transaction = EFTTransaction()
    eft_transaction.file_id = eft_file.id
    eft_transaction.line_number = 1
    eft_transaction.line_type = EFTFileLineType.HEADER.value
    eft_transaction.status_code = EFTProcessStatus.COMPLETED.value
    eft_transaction.save()

    eft_credit = EFTCredit()
    eft_credit.eft_file_id = eft_file.id
    eft_credit.short_name_id = eft_short_name.id
    eft_credit.amount = 100.00
    eft_credit.remaining_amount = 50.00
    eft_credit.eft_transaction_id = eft_transaction.id
    eft_credit.save()

    eft_credit.payment_account_id = payment_account.id
    eft_credit.save()

    link_group_id = EFTCreditInvoiceLink.get_next_group_link_seq()
    eft_credit_invoice_link = EFTCreditInvoiceLink()
    eft_credit_invoice_link.invoice_id = invoice.id
    eft_credit_invoice_link.eft_credit_id = eft_credit.id
    eft_credit_invoice_link.status_code = EFTCreditInvoiceStatus.PENDING.value
    eft_credit_invoice_link.amount = 50.00
    eft_credit_invoice_link.link_group_id = link_group_id
    eft_credit_invoice_link.save()

    eft_credit_invoice_link = EFTCreditInvoiceLink.find_by_id(eft_credit_invoice_link.id)
    assert eft_credit_invoice_link.id is not None
    assert eft_credit_invoice_link.eft_credit_id == eft_credit.id
    assert eft_credit_invoice_link.invoice_id == invoice.id
    assert eft_credit_invoice_link.status_code == EFTCreditInvoiceStatus.PENDING.value
    assert eft_credit_invoice_link.amount == 50.00
    assert eft_credit_invoice_link.link_group_id == link_group_id
