# src/consumers.py
import logging
import threading
import time

from .broker import Broker
from .metrics import Metrics
from .offsets import OffsetStore
from .storage import Storage

log = logging.getLogger("consumers")


def assign(num_partitions: int, consumer_ids: list[str]) -> dict[str, list[int]]:
    """
    Assignation round-robin des partitions aux consumers du groupe.
    Règle fondamentale : une partition est assignée à UN SEUL consumer à la fois.

    Exemple : 6 partitions, 3 consumers → C0:[0,3], C1:[1,4], C2:[2,5]
    Si consumers > partitions, certains consumers restent inactifs.
    """
    assignment: dict[str, list[int]] = {cid: [] for cid in consumer_ids}
    for p in range(num_partitions):
        cid = consumer_ids[p % len(consumer_ids)]
        assignment[cid].append(p)
    return assignment


class Consumer(threading.Thread):
    """
    Consumer worker : lit les partitions qui lui sont assignées,
    traite chaque événement, met à jour l'offset, et persiste
    périodiquement sur disque selon commit_every.
    """

    def __init__(
        self,
        cid: str,
        partitions: list[int],
        broker: Broker,
        offsets: OffsetStore,
        storage: Storage,
        metrics: Metrics,
        group: str,
        delay_ms: int = 30,
        commit_every: int = 5,
        stop_event: threading.Event = None,
    ):
        super().__init__(name=cid, daemon=True)
        self.cid = cid
        self.partitions = partitions
        self.broker = broker
        self.offsets = offsets
        self.storage = storage
        self.metrics = metrics
        self.group = group
        self.delay = delay_ms / 1000
        self.commit_every = commit_every
        self.stop_event = stop_event or threading.Event()

    def run(self) -> None:
        log.info("[%s] démarrage — partitions assignées : %s", self.cid, self.partitions)
        counters = {p: 0 for p in self.partitions}

        while not self.stop_event.is_set():
            progressed = False

            for p in self.partitions:
                off = self.offsets.get(self.group, p)
                evt = self.broker.fetch(p, off)
                if evt is None:
                    continue

                # Traitement : écriture sur disque + enregistrement métriques
                self.storage.write(evt, p)
                self.metrics.mark_processed(self.cid, p)
                time.sleep(self.delay)

                new_off = off + 1
                counters[p] += 1

                # Commit périodique sur disque ; entre deux commits, mise à jour mémoire
                if counters[p] % self.commit_every == 0:
                    self.offsets.commit(self.group, p, new_off)
                    log.debug("[%s] commit offset partition=%d → %d", self.cid, p, new_off)
                else:
                    self.offsets.set_memory(self.group, p, new_off)

                progressed = True

            if not progressed:
                # Aucune partition n'avait de nouveaux messages : petite pause
                time.sleep(0.05)

        # Flush final : on persiste l'état exact avant de quitter
        for p in self.partitions:
            self.offsets.flush(self.group, p)
        log.info("[%s] arrêt propre — offsets flushés", self.cid)
