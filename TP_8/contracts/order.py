# contracts/order.py
from dataclasses import dataclass, asdict, field
from datetime import datetime
import json, uuid

CITIES_AUTORISEES = {"Fes", "Casablanca", "Rabat", "Marrakech", "Tanger"}
STATUTS_AUTORISES = {"created", "confirmed", "prepared", "dispatched", "delivered", "cancelled", "failed"}

@dataclass
class Order:
    customer_id: str
    city: str
    zone: str
    courier_id: str
    amount: float
    items_count: int
    status: str = "created"
    order_id: str = field(default_factory=lambda: f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}")
    order_time: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "Order":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, s: str) -> "Order":
        return cls.from_dict(json.loads(s))


def validate_order(data: dict) -> None:
    required = ["customer_id", "city", "zone", "courier_id", "amount", "items_count"]
    for field in required:
        if field not in data:
            raise ValueError(f"Champ obligatoire manquant : '{field}'")
    if data["city"] not in CITIES_AUTORISEES:
        raise ValueError(f"Ville inconnue : '{data['city']}'. Villes autorisées : {CITIES_AUTORISEES}")
    if not isinstance(data["amount"], (int, float)) or data["amount"] <= 0:
        raise ValueError(f"Le montant doit être strictement positif, reçu : {data['amount']}")
    if not isinstance(data["items_count"], int) or data["items_count"] < 1:
        raise ValueError(f"items_count doit être un entier >= 1, reçu : {data['items_count']}")
    if "status" in data and data["status"] not in STATUTS_AUTORISES:
        raise ValueError(f"Statut invalide : '{data['status']}'. Statuts autorisés : {STATUTS_AUTORISES}")
