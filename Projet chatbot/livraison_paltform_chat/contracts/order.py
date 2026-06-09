"""Contrat de données pour une commande."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class OrderStatus(Enum):
    """Statuts possibles d'une commande."""
    CREATED = "created"
    CONFIRMED = "confirmed"
    PREPARED = "prepared"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ValidationError(Exception):
    """Exception levée lorsque la validation d'une commande échoue."""
    pass


@dataclass
class Order:
    """
    Contrat de données pour une commande.
    
    Attributs:
        order_id: Identifiant unique de la commande
        customer_id: Identifiant du client
        city: Ville de livraison
        zone: Zone dans la ville
        courier_id: Identifiant du livreur
        amount: Montant total de la commande (> 0)
        items_count: Nombre d'articles (> 0)
        status: Statut actuel de la commande
        created_at: Date/heure de création
    """
    
    order_id: str
    customer_id: str
    city: str
    zone: str
    courier_id: str
    amount: float
    items_count: int
    status: OrderStatus
    created_at: Optional[str] = None
    
    ALLOWED_CITIES = {'Fes', 'Casablanca', 'Rabat', 'Marrakech', 'Tanger'}
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = OrderStatus(data['status'])
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Order':
        data = json.loads(json_str)
        return cls.from_dict(data)


class OrderValidator:
    """Validateur pour les commandes."""
    
    @staticmethod
    def validate(order_data: Dict[str, Any]) -> Order:
        """Valide les données d'une commande."""
        required_fields = ['customer_id', 'city', 'zone', 'courier_id', 'amount', 'items_count']
        for field in required_fields:
            if field not in order_data:
                raise ValidationError(f"Champ obligatoire manquant: {field}")
        
        # Validation customer_id
        if not isinstance(order_data['customer_id'], str) or len(order_data['customer_id']) < 3:
            raise ValidationError("customer_id doit être une chaîne d'au moins 3 caractères")
        
        # Validation city
        city = order_data['city']
        if city not in Order.ALLOWED_CITIES:
            raise ValidationError(f"Ville non autorisée: {city}")
        
        # Validation zone
        if not isinstance(order_data['zone'], str) or len(order_data['zone']) < 2:
            raise ValidationError("zone doit être une chaîne d'au moins 2 caractères")
        
        # Validation courier_id
        if not isinstance(order_data['courier_id'], str) or not order_data['courier_id'].startswith('CRR-'):
            raise ValidationError("courier_id doit commencer par 'CRR-'")
        
        # Validation amount
        try:
            amount = float(order_data['amount'])
            if amount <= 0:
                raise ValidationError(f"amount doit être strictement positif, reçu: {amount}")
            if amount > 100000:
                raise ValidationError(f"amount ne peut pas dépasser 100000, reçu: {amount}")
        except (TypeError, ValueError):
            raise ValidationError(f"amount doit être un nombre valide, reçu: {order_data['amount']}")
        
        # Validation items_count
        try:
            items_count = int(order_data['items_count'])
            if items_count <= 0:
                raise ValidationError(f"items_count doit être strictement positif, reçu: {items_count}")
            if items_count > 100:
                raise ValidationError(f"items_count ne peut pas dépasser 100, reçu: {items_count}")
        except (TypeError, ValueError):
            raise ValidationError(f"items_count doit être un entier valide, reçu: {order_data['items_count']}")
        
        # Création de l'objet Order
        return Order(
            order_id="",
            customer_id=order_data['customer_id'],
            city=city,
            zone=order_data['zone'],
            courier_id=order_data['courier_id'],
            amount=amount,
            items_count=items_count,
            status=OrderStatus.CREATED
        )