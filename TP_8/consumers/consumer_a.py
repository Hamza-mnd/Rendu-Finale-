# consumers/consumer_a.py — Suivi par statut et par ville
import threading, time, logging
from collections import defaultdict
from broker.mini_broker import MiniBroker
from offsets.offset_store import OffsetStore
from storage.partitioned_store import PartitionedStore

log = logging.getLogger("consumer_a")
GROUP = "group-a"


class ConsumerA(threading.Thread):
    """
    Consumer A : agrège les commandes par statut et par ville.
    Lit ses partitions assignées, persiste les offsets toutes les 5 lectures.
    """

    def __init__(self, partitions: list[int], broker: MiniBroker,
                 offsets: OffsetStore, storage: PartitionedStore,
                 stop_event: threading.Event, commit_every: int = 5):
        super().__init__(name="ConsumerA", daemon=True)
        self.partitions = partitions
        self.broker = broker
        self.offsets = offsets
        self.storage = storage
        self.stop_event = stop_event
        self.commit_every = commit_every
        # Agrégats
        self.by_status: dict[str, int] = defaultdict(int)
        self.by_city: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
        self._counters = {p: 0 for p in partitions}

    def run(self) -> None:
        log.info("[A] démarrage — partitions : %s", self.partitions)
        while not self.stop_event.is_set():
            progressed = False
            for p in self.partitions:
                off = self.offsets.get(GROUP, p)
                evt = self.broker.fetch(p, off)
                if evt is None:
                    continue
                try:
                    self._process(evt, p, off + 1)
                    progressed = True
                except Exception as e:
                    log.error("[A] erreur sur partition=%d offset=%d : %s", p, off, e)
                    self.offsets.set_memory(GROUP, p, off + 1)
            if not progressed:
                time.sleep(0.05)
        for p in self.partitions:
            self.offsets.flush(GROUP, p)
        log.info("[A] arrêt propre")

    def _process(self, evt, partition: int, new_off: int) -> None:
        with self._lock:
            self.by_status[evt.status] += 1
            self.by_city[evt.city] += 1
        self.storage.write(evt, partition)
        self._counters[partition] += 1
        if self._counters[partition] % self.commit_every == 0:
            self.offsets.commit(GROUP, partition, new_off)
        else:
            self.offsets.set_memory(GROUP, partition, new_off)
        log.debug("[A] traité %s city=%s status=%s off=%d", evt.order_id, evt.city, evt.status, new_off)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "by_status": dict(self.by_status),
                "by_city": dict(self.by_city),
            }
