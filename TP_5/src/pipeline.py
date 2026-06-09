"""pipeline.py — Queues + coordination du pipeline (Séance 5)."""
import queue
import threading


class Pipeline:
    """Conteneur des files et du signal d'arrêt partagé.

    Attributes:
        main_queue:        Queue principale bornée (backpressure).
        dead_letter_queue: Queue sans limite pour les messages échoués.
        stop_event:        Event partagé pour arrêt propre des threads.
        threads:           Liste des threads workers/monitor.
        _worker_count:     Compteur de workers actifs (scale-out).
    """

    MAX_WORKERS = 5  # Limite du scale-out automatique

    def __init__(self, maxsize: int = 50):
        self.main_queue        = queue.Queue(maxsize=maxsize)
        self.dead_letter_queue = queue.Queue()
        self.stop_event        = threading.Event()
        self.threads:          list[threading.Thread] = []
        self._worker_count     = 0
        self._lock             = threading.Lock()

    def add_thread(self, t: threading.Thread) -> None:
        """Enregistre un thread pour la gestion du shutdown."""
        self.threads.append(t)

    def increment_workers(self) -> bool:
        """Incrémente le compteur de workers. Retourne False si MAX atteint."""
        with self._lock:
            if self._worker_count >= self.MAX_WORKERS:
                return False
            self._worker_count += 1
            return True

    def shutdown(self, timeout: float = 10) -> None:
        """Arrêt propre : signale l'arrêt et attend tous les threads."""
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=timeout)
