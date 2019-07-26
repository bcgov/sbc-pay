import json

import pytest
from flask import current_app
from unittest.mock import patch

from .utils import subscribe_to_queue


@pytest.mark.asyncio
async def test_publish(app, stan_server, client_id, stan, future, event_loop):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    with app.app_context():
        # Call back for the subscription
        async def subscriber_callback(msg):
            current_app.logger.debug('Inside Call Back')
            current_app.logger.debug(msg.data.decode('utf-8'))
            message_dict = json.loads(msg.data.decode('utf-8'))
            assert 'paymentToken' in message_dict
            current_app.logger.debug(message_dict['paymentToken']['statusCode'])
            assert 'COMPLETED' == message_dict['paymentToken']['statusCode']

        await subscribe_to_queue(stan, subscriber_callback)

        # publish message
        from pay_api.services.queue_publisher import publish
        payload = {
            'paymentToken': {
                'id': 1,
                'statusCode': 'COMPLETED'
            }
        }

        await publish(payload=payload)


@pytest.mark.asyncio
async def test_publish_transaction_failed(app, client_id, stan, future, stan_server):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    with app.app_context():
        # Call back for the subscription
        async def subscriber_callback(msg):
            current_app.logger.debug('Inside Call Back')
            current_app.logger.debug(msg.data.decode('utf-8'))
            message_dict = json.loads(msg.data.decode('utf-8'))
            assert 'paymentToken' in message_dict
            current_app.logger.debug(message_dict['paymentToken']['statusCode'])
            assert 'TRANSACTION_FAILED' == message_dict['paymentToken']['statusCode']

        await subscribe_to_queue(stan, subscriber_callback)

        # publish message
        from pay_api.services.queue_publisher import publish
        payload = {
            'paymentToken': {
                'id': 100,
                'statusCode': 'TRANSACTION_FAILED'
            }
        }

        await publish(payload=payload)


@pytest.mark.asyncio
async def test_publish_transaction_bulk_load(app, client_id, stan, future, stan_server):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    with app.app_context():
        # Call back for the subscription
        async def subscriber_callback(msg):
            current_app.logger.debug('Inside Call Back')
            current_app.logger.debug(msg.data.decode('utf-8'))
            message_dict = json.loads(msg.data.decode('utf-8'))
            assert 'paymentToken' in message_dict
            current_app.logger.debug(message_dict['paymentToken']['statusCode'])
            assert 'COMPLETED' == message_dict['paymentToken']['statusCode']

        await subscribe_to_queue(stan, subscriber_callback)

        # publish message
        from pay_api.services.queue_publisher import publish
        for i in range(10):
            payload = {
                'paymentToken': {
                    'id': i,
                    'statusCode': 'COMPLETED'
                }
            }
            await publish(payload=payload)


@pytest.mark.asyncio
async def test_publish_transaction_nats_down(app, client_id, stan, future, stan_server):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    with app.app_context():
        # Call back for the subscription
        nats_connect = patch('nats.aio.client.Client.connect')

        mock = nats_connect.start()
        mock.side_effect = Exception()

        # publish message
        from pay_api.services.queue_publisher import publish
        payload = {
            'paymentToken': {
                'id': 10,
                'statusCode': 'COMPLETED'
            }
        }
        with pytest.raises(Exception) as excinfo:
            await publish(payload=payload)
        mock.stop()
