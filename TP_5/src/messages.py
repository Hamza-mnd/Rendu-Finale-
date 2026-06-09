"""messages.py — Contrat d'enveloppe de message pour le pipeline IoT (Séance 5)."""
from dataclasses import dataclass, field, asdict
from typing import Any
import uuid
import time


@dataclass
class EventMessage:
    """Enveloppe standard pour tous les messages du pipeline.

    Champs :
        msg_id        : UUID unique (déduplication, corrélation).
        msg_type      : type de message (ex. 'sensor_reading').
        payload       : données métier.
        created_at    : timestamp de création (calcul de latence).
        attempts      : nombre de tentatives effectuées.
        max_attempts  : seuil avant dead-letter queue.
    """
    msg_id:       str   = field(default_factory=lambda: str(uuid.uuid4()))
    msg_type:     str   = "sensor_reading"
    payload:      dict  = field(default_factory=dict)
    created_at:   float = field(default_factory=time.time)
    attempts:     int   = 0
    max_attempts: int   = 3

    def should_retry(self) -> bool:
        """True si le nombre de tentatives n'a pas atteint le maximum."""
        return self.attempts < self.max_attempts

    def to_dict(self) -> dict:
        """Sérialise le message en dictionnaire JSON-compatible."""
        return asdict(self)
