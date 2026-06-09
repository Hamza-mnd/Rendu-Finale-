# broker/mini_broker.py
import hashlib, threading
from typing import Optional
from contracts.event import OrderEvent

NUM_PARTITIONS = 4  # configurable

def partition_of(key: str, num_partitions: int = NUM_PARTITIONS) -> int:
    """Routage déterministe par hachage SHA-256."""
    h = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % num_partitions


class MiniBroker:
    """
    Broker en mémoire simulant NUM_PARTITIONS partitions append-only.
    La clé de partition est city — garantit que tous les événements
    d'une même ville sont ordonnés dans la même partition.
    """

    def __init__(self, num_partitions: int = NUM_PARTITIONS):
        self.num_partitions = num_partitions
        self.partitions: list[list[OrderEvent]] = [[] for _ in range(num_partitions)]
        self._lock = threading.Lock()

    def publish(self, event: OrderEvent) -> tuple[int, int]:
        """Publie un événement. Retourne (partition, offset)."""
        p = partition_of(event.city, self.num_partitions)
        with self._lock:
            self.partitions[p].append(event)
            offset = len(self.partitions[p]) - 1
        return p, offset

    def fetch(self, partition: int, offset: int) -> Optional[OrderEvent]:
        with self._lock:
            if 0 <= offset < len(self.partitions[partition]):
                return self.partitions[partition][offset]
        return None

    def size(self, partition: int) -> int:
        with self._lock:
            return len(self.partitions[partition])

    def summary(self) -> dict:
        return {p: self.size(p) for p in range(self.num_partitions)}

    def lag(self, offsets: dict, group: str) -> dict:
        """Calcule le lag (backlog) par partition pour un groupe."""
        result = {}
        for p in range(self.num_partitions):
            committed = offsets.get(group, {}).get(str(p), 0)
            result[p] = max(0, self.size(p) - committed)
        return result
