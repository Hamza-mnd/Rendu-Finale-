# src/broker.py
import threading
from typing import Optional

from .events import Event
from .partitioner import partition_of


class Broker:
    """
    Broker en mémoire simulant N partitions indépendantes.
    Chaque partition est une liste ordonnée d'événements (append-only).
    Le routage se fait par hachage de la clé de partition.
    """

    def __init__(self, num_partitions: int, key_field: str = "sensor_id"):
        self.num_partitions = num_partitions
        self.key_field = key_field
        self.partitions: list[list[Event]] = [[] for _ in range(num_partitions)]
        self._lock = threading.Lock()

    def publish(self, event: Event) -> int:
        """Publie un événement dans la partition correspondant à sa clé. Retourne l'id de partition."""
        key = event.partition_key(self.key_field)
        p = partition_of(key, self.num_partitions)
        with self._lock:
            self.partitions[p].append(event)
        return p

    def fetch(self, partition: int, offset: int) -> Optional[Event]:
        """Retourne l'événement à l'offset donné dans la partition, ou None si absent."""
        with self._lock:
            if 0 <= offset < len(self.partitions[partition]):
                return self.partitions[partition][offset]
        return None

    def size(self, partition: int) -> int:
        """Retourne le nombre d'événements dans la partition (taille totale)."""
        with self._lock:
            return len(self.partitions[partition])

    def summary(self) -> dict:
        """Retourne un résumé : taille de chaque partition."""
        return {p: self.size(p) for p in range(self.num_partitions)}
