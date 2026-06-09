"""Contrat de données pour un événement métier."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum


class EventType(Enum):
    """Types d'événements métier."""
    ORDER_CREATED = "order_created"
    ORDER_CONFIRMED = "order_confirmed"
    ORDER_PREPARED = "order_prepared"
    ORDER_DISPATCHED = "order_dispatched"
    ORDER_DELIVERED = "order_delivered"
    ORDER_CANCELLED = "order_cancelled"
    DELIVERY_FAILED = "delivery_failed"


class EventValidationError(Exception):
    """Exception levée lorsque la validation d'un événement échoue."""
    pass


@dataclass
class OrderEvent:
    """
    Contrat de données pour un événement métier.
    
    Attributs communs à tous les événements:
        event_id: Identifiant unique de l'événement
        order_id: Identifiant de la commande concernée
        event_type: Type d'événement
        event_time: Horodatage de l'événement
        partition_key: Clé de partition (city)
        
    Attributs spécifiques (optionnels selon le type):
        failure_reason: Raison de l'échec (pour delivery_failed)
        cancellation_reason: Raison de l'annulation (pour order_cancelled)
        courier_id: Identifiant du livreur
        city: Ville
        zone: Zone
        amount: Montant
        items_count: Nombre d'articles
    """
    
    event_id: str
    order_id: str
    event_type: EventType
    event_time: str
    partition_key: str
    
    # Champs optionnels spécifiques à certains événements
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    courier_id: Optional[str] = None
    city: Optional[str] = None
    zone: Optional[str] = None
    amount: Optional[float] = None
    items_count: Optional[int] = None
    status: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire pour sérialisation."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        return data
    
    def to_json(self) -> str:
        """Sérialise l'objet en JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderEvent':
        """Crée une instance OrderEvent à partir d'un dictionnaire."""
        if 'event_type' in data and isinstance(data['event_type'], str):
            data['event_type'] = EventType(data['event_type'])
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'OrderEvent':
        """Crée une instance OrderEvent à partir d'une chaîne JSON."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class EventValidator:
    """Validateur pour les événements métier."""
    
    @staticmethod
    def validate(event_data: Dict[str, Any]) -> OrderEvent:
        """
        Valide les données d'un événement.
        
        Args:
            event_data: Dictionnaire contenant les données de l'événement
            
        Returns:
            OrderEvent: Instance validée de OrderEvent
            
        Raises:
            EventValidationError: Si une validation échoue
        """
        # Vérification des champs obligatoires
        required_fields = ['order_id', 'event_type', 'partition_key']
        for field in required_fields:
            if field not in event_data:
                raise EventValidationError(f"Champ obligatoire manquant: {field}")
        
        # Validation event_type
        try:
            event_type = EventType(event_data['event_type'])
        except ValueError:
            raise EventValidationError(f"Type d'événement invalide: {event_data['event_type']}")
        
        # Validation partition_key
        partition_key = event_data['partition_key']
        allowed_cities = {'Fes', 'Casablanca', 'Rabat', 'Marrakech', 'Tanger'}
        if partition_key not in allowed_cities:
            raise EventValidationError(f"Clé de partition invalide: {partition_key}")
        
        # Validation spécifique selon le type
        if event_type == EventType.DELIVERY_FAILED and 'failure_reason' not in event_data:
            raise EventValidationError("Pour delivery_failed, failure_reason est obligatoire")
        
        if event_type == EventType.ORDER_CANCELLED and 'cancellation_reason' not in event_data:
            raise EventValidationError("Pour order_cancelled, cancellation_reason est obligatoire")
        
        # Génération d'un event_id et event_time si non fournis
        event_id = event_data.get('event_id', f"EVT-{datetime.now().timestamp()}")
        event_time = event_data.get('event_time', datetime.now().isoformat())
        
        return OrderEvent(
            event_id=event_id,
            order_id=event_data['order_id'],
            event_type=event_type,
            event_time=event_time,
            partition_key=partition_key,
            failure_reason=event_data.get('failure_reason'),
            cancellation_reason=event_data.get('cancellation_reason'),
            courier_id=event_data.get('courier_id'),
            city=event_data.get('city'),
            zone=event_data.get('zone'),
            amount=event_data.get('amount'),
            items_count=event_data.get('items_count'),
            status=event_data.get('status')
        )