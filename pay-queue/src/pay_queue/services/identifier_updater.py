from flask import current_app
from pay_api.models.invoice import Invoice
from pay_api.models import db


def update_temporary_identifier(event_message):
  if not 'tempidentifier' in event_message or event_message.get('tempidentifier', None) is None:
    return

  old_identifier = event_message.get('tempidentifier')
  new_identifier = event_message.get('identifier')
  current_app.logger.debug('Received message to update %s to %s', old_identifier, new_identifier)

  # Find all invoice records which have the old corp number
  invoices = Invoice.find_by_business_identifier(old_identifier)
  for inv in invoices:
      inv.business_identifier = new_identifier
      inv.flush()

  db.session.commit()
