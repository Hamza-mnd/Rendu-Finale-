"""source.py — Générateur d'événements vers la queue (Séance 6)."""
import queue
import threading
import time
import logging

logger = logging.getLogger(__name__)


class EventSource:
    """Lit une liste d'événements JSON et les envoie dans une queue avec délai.

    Simule un flux IoT réel : chaque événement est émis avec un
    délai `delay` secondes, reproduisant l'arrivée en processing time.
    L'ordre d'émission peut différer de l'event_time (out-of-order).

    Args:
        events_json: Liste de dicts bruts (JSON des événements).
        q:           Queue cible (bornée ou non).
        delay:       Délai entre deux événements en secondes.
    """

    def __init__(self, events_json: list[dict], q: queue.Queue,
                 delay: float = 0.3):
        self.events = events_json
        self.queue  = q
        self.delay  = delay

    def run(self):
        """Produit tous les événements puis envoie le sentinel None."""
        for raw in self.events:
            self.queue.put(raw)
            logger.info("Source: émis %s (event_time=%s)",
                        raw["event_id"], raw["event_time"])
            time.sleep(self.delay)
        self.queue.put(None)   # sentinel → fin du flux
        logger.info("Source: flux terminé (sentinel envoyé)")

    def start(self) -> threading.Thread:
        """Lance la source dans un thread daemon et retourne le thread."""
        t = threading.Thread(target=self.run, daemon=True, name="source")
        t.start()
        return t
