# service/order_service.py
import logging, uuid
from typing import Optional
from datetime import datetime
from contracts.order import Order, validate_order
from contracts.event import OrderEvent, validate_event
from broker.mini_broker import MiniBroker

log = logging.getLogger("order_service")


class OrderService:
    """
    Service synchrone de réception et validation de commandes.
    Retourne immédiatement une réponse (succès + order_id, ou erreur détaillée).
    Publie un événement order_created dans le broker en cas de succès.
    """

    def __init__(self, broker: MiniBroker):
        self.broker = broker
        self._orders: dict[str, Order] = {}

    def create_order(self, data: dict) -> dict:
        # 1. Validation
        try:
            validate_order(data)
        except ValueError as e:
            log.warning("Validation échouée : %s", e)
            return {"status": "error", "message": str(e)}

        # 2. Création de la commande
        order = Order(**{k: v for k, v in data.items() if k in Order.__dataclass_fields__})
        self._orders[order.order_id] = order
        log.info("Commande créée : %s (ville=%s, montant=%.2f)", order.order_id, order.city, order.amount)

        # 3. Publication de l'événement order_created
        event = OrderEvent(
            event_type="order_created",
            order_id=order.order_id,
            city=order.city,
            zone=order.zone,
            courier_id=order.courier_id,
            amount=order.amount,
            status="created",
        )
        p, offset = self.broker.publish(event)
        log.info("Événement publié → partition=%d offset=%d", p, offset)

        return {"status": "accepted", "order_id": order.order_id, "partition": p, "offset": offset}

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def known_orders(self) -> set[str]:
        return set(self._orders.keys())
