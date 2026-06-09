# consumers/consumer_b.py — Suivi par livreur
import threading, time, logging
from collections import defaultdict
from broker.mini_broker import MiniBroker
from offsets.offset_store import OffsetStore
from storage.partitioned_store import PartitionedStore

log = logging.getLogger("consumer_b")
GROUP = "group-b"


class ConsumerB(threading.Thread):
    """
    Consumer B : agrège les livraisons par livreur (activité, succès, échecs).
    """

    def __init__(self, partitions: list[int], broker: MiniBroker,
                 offsets: OffsetStore, storage: PartitionedStore,
                 stop_event: threading.Event, commit_every: int = 5):
        super().__init__(name="ConsumerB", daemon=True)
        self.partitions = partitions
        self.broker = broker
        self.offsets = offsets
        self.storage = storage
        self.stop_event = stop_event
        self.commit_every = commit_every
        # Agrégats livreur
        self.by_courier: dict[str, dict] = defaultdict(lambda: {"total": 0, "delivered": 0, "failed": 0})
        self._lock = threading.Lock()
        self._counters = {p: 0 for p in partitions}

    def run(self) -> None:
        log.info("[B] démarrage — partitions : %s", self.partitions)
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
                    log.error("[B] erreur partition=%d offset=%d : %s", p, off, e)
                    self.offsets.set_memory(GROUP, p, off + 1)
            if not progressed:
                time.sleep(0.05)
        for p in self.partitions:
            self.offsets.flush(GROUP, p)
        log.info("[B] arrêt propre")

    def _process(self, evt, partition: int, new_off: int) -> None:
        with self._lock:
            c = self.by_courier[evt.courier_id]
            c["total"] += 1
            if evt.status == "delivered":
                c["delivered"] += 1
            elif evt.status == "failed":
                c["failed"] += 1
        self._counters[partition] += 1
        if self._counters[partition] % self.commit_every == 0:
            self.offsets.commit(GROUP, partition, new_off)
        else:
            self.offsets.set_memory(GROUP, partition, new_off)
        log.debug("[B] livreur=%s total=%d off=%d", evt.courier_id, self.by_courier[evt.courier_id]["total"], new_off)

    def snapshot(self) -> dict:
        with self._lock:
            return {"by_courier": {k: dict(v) for k, v in self.by_courier.items()}}
