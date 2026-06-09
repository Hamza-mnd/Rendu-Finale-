"""metrics.py — Compteurs thread-safe + dashboard (Séance 5)."""
import threading
import time
import queue as queue_mod
import logging


class PipelineMetrics:
    """Collecteur thread-safe de métriques du pipeline.

    Métriques suivies :
        success      : messages traités avec succès.
        failures     : messages envoyés en DLQ.
        retries      : tentatives de retry.
        total_latency: somme des latences (pour calcul de moyenne).
        start_time   : début du pipeline (pour le débit).
    """

    def __init__(self):
        self._lock         = threading.Lock()
        self.success       = 0
        self.failures      = 0
        self.retries       = 0
        self.total_latency = 0.0
        self.start_time    = time.time()

    def record_success(self, latency: float):
        with self._lock:
            self.success       += 1
            self.total_latency += latency

    def record_failure(self):
        with self._lock:
            self.failures += 1

    def record_retry(self):
        with self._lock:
            self.retries += 1

    def snapshot(self) -> dict:
        """Retourne une copie figée des métriques (thread-safe)."""
        with self._lock:
            elapsed  = time.time() - self.start_time
            rate     = self.success / elapsed if elapsed > 0 else 0
            avg_lat  = (self.total_latency / self.success) if self.success else 0
            return {
                "success":        self.success,
                "failures":       self.failures,
                "retries":        self.retries,
                "rate_per_sec":   round(rate, 1),
                "avg_latency_ms": round(avg_lat * 1000, 1),
                "elapsed_sec":    round(elapsed, 1),
            }


def monitor_loop(q: queue_mod.Queue, metrics: PipelineMetrics,
                 stop: threading.Event, interval: float = 2,
                 scale_out_fn=None, backlog_threshold: int = 40) -> None:
    """Affiche un dashboard texte et déclenche le scale-out si nécessaire.

    Args:
        q:                  Queue principale (pour backlog).
        metrics:            Métriques du pipeline.
        stop:               Event d'arrêt.
        interval:           Intervalle d'affichage (secondes).
        scale_out_fn:       Fonction appelée si backlog > seuil (optionnel).
        backlog_threshold:  Seuil de déclenchement du scale-out.
    """
    while not stop.is_set():
        s       = metrics.snapshot()
        backlog = q.qsize()
        print(
            f"[DASHBOARD] backlog={backlog:>4} | "
            f"success={s['success']:>5} | fail={s['failures']:>3} | "
            f"retry={s['retries']:>3} | rate={s['rate_per_sec']:>6.1f} msg/s | "
            f"latency={s['avg_latency_ms']:>7.1f}ms"
        )
        # Scale-out automatique (bonus)
        if scale_out_fn and backlog > backlog_threshold:
            scale_out_fn()
        time.sleep(interval)
