# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to manage BCOL Payments."""

import zeep
from flask import current_app

from bcol_api.exceptions import BusinessException, PaymentException
from bcol_api.services.bcol_soap import BcolSoap
from bcol_api.utils.errors import Error


class BcolPayment:  # pylint:disable=too-few-public-methods
    """Service to manage BCOL Payments."""

    def create_payment(self, pay_request: dict, is_apply_charge: bool):
        """Create payment record in BCOL."""
        current_app.logger.debug(f"<create_payment {pay_request.get('invoiceNumber')}")
        padded_amount = self._pad_zeros(pay_request.get("amount", "0"))
        # Call the query profile service to fetch profile
        data = {
            "Version": current_app.config.get("BCOL_DEBIT_ACCOUNT_VERSION"),
            "Feecode": pay_request.get("feeCode"),
            "Userid": pay_request.get("userId"),
            "Key": pay_request.get("invoiceNumber"),
            "Account": pay_request.get("accountNumber", ""),
            "RateType": pay_request.get("rateType", ""),
            "Folio": pay_request.get("folioNumber", None),
            "FormNumber": pay_request.get("formNumber", ""),  # Also DAT Number
            "Quantity": pay_request.get("quantity", ""),
            "Rate": padded_amount,
            "Amount": padded_amount,
            "Remarks": pay_request.get("remarks", "BCOL Payment from BCROS"),
            "RedundantFlag": pay_request.get("reduntantFlag", " "),
            "linkcode": current_app.config.get("BCOL_LINK_CODE"),
        }

        try:
            current_app.logger.debug(f"Is staff payment ? = {is_apply_charge} ")

            response = self.apply_charge(data) if is_apply_charge else self.debit_account(data)
            current_app.logger.debug(response)

            if self.__get(response, "ReturnCode") != "0000":
                raise BusinessException(Error.PAYMENT_ERROR)

            ts_fee = self.__get(response, "TSFee")
            invoice_service_fees = pay_request.get("serviceFees", "0")
            self._check_service_fees_match(ts_fee, invoice_service_fees)

            transaction = response["TranID"]
            pay_response = {
                "statutoryFee": self.__get(response, "StatFee"),
                "totalAmount": self.__get(response, "Totamt"),
                "tsFee": ts_fee,
                "gst": self.__get(response, "Totgst"),
                "pst": self.__get(response, "Totpst"),
                "accountNumber": self.__get(transaction, "Account"),
                "userId": self.__get(transaction, "UserID"),
                "date": self.__get(transaction, "AppliedDate") + ":" + self.__get(transaction, "AppliedTime"),
                "feeCode": self.__get(transaction, "FeeCode"),
                "key": self.__get(transaction, "Key"),
                "sequenceNo": self.__get(transaction, "SequenceNo"),
            }

        except zeep.exceptions.Fault as fault:
            current_app.logger.error(fault)
            if is_apply_charge:
                parsed_fault_detail = BcolSoap().get_applied_chg_client().wsdl.types.deserialize(fault.detail[0])
            else:
                parsed_fault_detail = BcolSoap().get_payment_client().wsdl.types.deserialize(fault.detail[0])
            current_app.logger.error(parsed_fault_detail)
            raise PaymentException(
                message=self.__get(parsed_fault_detail, "message"),
                code=self.__get(parsed_fault_detail, "returnCode"),
            ) from fault
        except BusinessException as e:
            raise e
        except Exception as e:  # NOQA
            current_app.logger.error(e)
            raise BusinessException(Error.PAYMENT_ERROR) from e

        current_app.logger.debug(">create_payment")
        return pay_response

    def __get(self, value: object, key: object) -> str:  # pragma: no cover
        """Get the value from dict and strip."""
        if value and value[key]:
            return value[key].strip() if isinstance(value[key], str) else value[key]
        return None

    def debit_account(self, data: dict):  # pragma: no cover
        """Debit BCOL account."""
        client = BcolSoap().get_payment_client()
        return zeep.helpers.serialize_object(client.service.debitAccount(req=data))

    def apply_charge(self, data: dict):  # pragma: no cover
        """Debit BCOL account as a staff user."""
        client = BcolSoap().get_applied_chg_client()
        return zeep.helpers.serialize_object(client.service.appliedCharge(req=data))

    def _pad_zeros(self, amount: str = "0"):
        """Pad the amount with Zeroes to make sure the string is 10 chars."""
        if not amount:
            return None
        amount = int(float(amount) * 100)  # Multiply with 100, as for e.g, 50.00 needs to be 5000
        return str(amount).zfill(10)

    def _check_service_fees_match(self, ts_fee, invoice_service_fees):
        """Check to see if BCOL return matches passed in service fees."""
        ts_fee = -float(ts_fee) / 100 if ts_fee else 0
        if ts_fee != float(invoice_service_fees):
            current_app.logger.error(
                f"TSFee {ts_fee} from BCOL doesn't match SBC-PAY invoice service fees: {invoice_service_fees}"
            )
