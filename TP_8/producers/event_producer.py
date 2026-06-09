# producers/event_producer.py
import logging, time
from datetime import datetime
from contracts.event import OrderEvent, validate_event
from broker.mini_broker import MiniBroker

log = logging.getLogger("producer")

# Cycle de vie d'une commande : ordre logique des événements
LIFECYCLE = [
    "order_created",
    "order_confirmed",
    "order_prepared",
    "order_dispatched",
    "order_delivered",
]


class EventProducer:
    """
    Producteur d'événements métier.
    Valide chaque événement avant publication.
    Retourne (partition, offset) à chaque publication.
    """

    def __init__(self, broker: MiniBroker):
        self.broker = broker

    def publish(self, event_type: str, order_id: str, city: str, zone: str,
                courier_id: str, amount: float, status: str) -> tuple[int, int]:
        data = {
            "event_type": event_type,
            "order_id": order_id,
            "city": city,
            "zone": zone,
            "courier_id": courier_id,
            "amount": amount,
            "status": status,
        }
        validate_event(data)
        event = OrderEvent(**data)
        p, offset = self.broker.publish(event)
        log.info("[PRODUCER] %s → order=%s city=%s partition=%d offset=%d",
                 event_type, order_id, city, p, offset)
        return p, offset

    def simulate_lifecycle(self, order_id: str, city: str, zone: str,
                           courier_id: str, amount: float, delay_s: float = 0.1) -> None:
        """Simule le cycle de vie complet d'une commande avec délai entre chaque étape."""
        statuses = ["created", "confirmed", "prepared", "dispatched", "delivered"]
        for event_type, status in zip(LIFECYCLE, statuses):
            self.publish(event_type, order_id, city, zone, courier_id, amount, status)
            time.sleep(delay_s)
