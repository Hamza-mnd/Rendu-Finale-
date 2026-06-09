"""metrics.py — Observabilité du pipeline streaming (Séance 6)."""
import time
import logging

logger = logging.getLogger(__name__)


class Metrics:
    """Collecte les latences et génère des rapports périodiques.

    Latence ici = processing_time - event_time (en secondes).
    Reflète le délai entre la mesure réelle et son traitement.
    """

    def __init__(self):
        self.start_time = time.time()
        self.latencies: list[float] = []

    def record_latency(self, event_time: float) -> None:
        """Enregistre la latence d'un événement (processing_time - event_time)."""
        self.latencies.append(time.time() - event_time)

    def report(self, processor, q_size: int) -> None:
        """Affiche un dashboard dans les logs avec les métriques clés.

        Indicateurs :
            elapsed      : durée depuis le démarrage.
            processed    : événements traités.
            throughput   : événements / seconde.
            avg_latency  : latence moyenne processing-event.
            backlog      : messages en attente dans la queue.
            late         : late-accepted count.
            dropped      : dropped count.
            state_keys   : nombre de fenêtres en cours (mémoire état).
        """
        elapsed    = time.time() - self.start_time
        throughput = processor.events_processed / max(elapsed, 0.01)
        avg_lat    = (
            sum(self.latencies) / len(self.latencies)
            if self.latencies else 0.0
        )
        logger.info(
            "[METRICS] elapsed=%.1fs | processed=%d | throughput=%.1f evt/s | "
            "avg_latency=%.2fs | backlog=%d | late=%d | dropped=%d | state_keys=%d",
            elapsed,
            processor.events_processed,
            throughput,
            avg_lat,
            q_size,
            len(processor.late_events),
            len(processor.dropped_events),
            len(processor.state),
        )
