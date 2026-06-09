# contracts/event.py
from dataclasses import dataclass, asdict, field
from datetime import datetime
import json

EVENT_TYPES = {
    "order_created", "order_confirmed", "order_prepared",
    "order_dispatched", "order_delivered", "order_cancelled", "delivery_failed"
}

@dataclass
class OrderEvent:
    event_type: str
    order_id: str
    city: str
    zone: str
    courier_id: str
    amount: float
    status: str
    event_time: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")
    write_time: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["write_time"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "OrderEvent":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, s: str) -> "OrderEvent":
        return cls.from_dict(json.loads(s))


def validate_event(data: dict) -> None:
    required = ["event_type", "order_id", "city", "courier_id", "amount", "status"]
    for f in required:
        if f not in data:
            raise ValueError(f"Champ événement manquant : '{f}'")
    if data["event_type"] not in EVENT_TYPES:
        raise ValueError(f"Type d'événement inconnu : '{data['event_type']}'. Types valides : {EVENT_TYPES}")
    if not data["order_id"].startswith("ORD-"):
        raise ValueError(f"order_id invalide : '{data['order_id']}' (doit commencer par ORD-)")
    if not isinstance(data["amount"], (int, float)) or data["amount"] <= 0:
        raise ValueError(f"Montant invalide dans l'événement : {data['amount']}")
