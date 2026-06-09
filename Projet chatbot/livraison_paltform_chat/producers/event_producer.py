"""Producteur d'événements métier."""

import time
import logging
from datetime import datetime
from typing import Dict, Any
from uuid import uuid4

from contracts import OrderEvent, EventType
from broker import MiniBroker, BrokerError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventProducer:
    """Producteur d'événements métier."""
    
    def __init__(self, broker: MiniBroker, max_retries: int = 3, retry_delay: float = 1.0):
        self.broker = broker
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def _generate_event_id(self) -> str:
        return f"EVT-{int(datetime.now().timestamp())}-{uuid4().hex[:8]}"
    
    def _publish_with_retry(self, event_data: Dict[str, Any], partition_key: str) -> tuple:
        for attempt in range(self.max_retries):
            try:
                partition, offset = self.broker.publish(event_data, partition_key)
                logger.info(f"✅ Événement publié: {event_data['event_type']} | order_id={event_data['order_id']}")
                return partition, offset
            except BrokerError as e:
                logger.warning(f"Tentative {attempt + 1}/{self.max_retries} échouée: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise
        return None, None
    
    def publish_order_created(self, order: Dict[str, Any]) -> tuple:
        event_data = {
            'event_id': self._generate_event_id(),
            'order_id': order['order_id'],
            'event_type': 'order_created',
            'event_time': datetime.now().isoformat(),
            'partition_key': order['city'],
            'courier_id': order.get('courier_id'),
            'city': order.get('city'),
            'zone': order.get('zone'),
            'amount': order.get('amount'),
            'items_count': order.get('items_count'),
            'status': 'created'
        }
        return self._publish_with_retry(event_data, order['city'])
    
    def publish_order_confirmed(self, order_id: str, city: str, **kwargs) -> tuple:
        event_data = {
            'event_id': self._generate_event_id(),
            'order_id': order_id,
            'event_type': 'order_confirmed',
            'event_time': datetime.now().isoformat(),
            'partition_key': city,
            **kwargs
        }
        return self._publish_with_retry(event_data, city)
    
    def publish_order_prepared(self, order_id: str, city: str, **kwargs) -> tuple:
        event_data = {
            'event_id': self._generate_event_id(),
            'order_id': order_id,
            'event_type': 'order_prepared',
            'event_time': datetime.now().isoformat(),
            'partition_key': city,
            **kwargs
        }
        return self._publish_with_retry(event_data, city)
    
    def publish_order_dispatched(self, order_id: str, city: str, **kwargs) -> tuple:
        event_data = {
            'event_id': self._generate_event_id(),
            'order_id': order_id,
            'event_type': 'order_dispatched',
            'event_time': datetime.now().isoformat(),
            'partition_key': city,
            **kwargs
        }
        return self._publish_with_retry(event_data, city)
    
    def publish_order_delivered(self, order_id: str, city: str, **kwargs) -> tuple:
        event_data = {
            'event_id': self._generate_event_id(),
            'order_id': order_id,
            'event_type': 'order_delivered',
            'event_time': datetime.now().isoformat(),
            'partition_key': city,
            **kwargs
        }
        return self._publish_with_retry(event_data, city)
    
    def publish_order_cancelled(self, order_id: str, city: str, cancellation_reason: str, **kwargs) -> tuple:
        event_data = {
            'event_id': self._generate_event_id(),
            'order_id': order_id,
            'event_type': 'order_cancelled',
            'event_time': datetime.now().isoformat(),
            'partition_key': city,
            'cancellation_reason': cancellation_reason,
            **kwargs
        }
        return self._publish_with_retry(event_data, city)
    
    def publish_delivery_failed(self, order_id: str, city: str, failure_reason: str, **kwargs) -> tuple:
        event_data = {
            'event_id': self._generate_event_id(),
            'order_id': order_id,
            'event_type': 'delivery_failed',
            'event_time': datetime.now().isoformat(),
            'partition_key': city,
            'failure_reason': failure_reason,
            **kwargs
        }
        return self._publish_with_retry(event_data, city)