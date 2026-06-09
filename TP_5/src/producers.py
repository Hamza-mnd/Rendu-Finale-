"""producers.py — Générateur de rafales de données IoT (Séance 5)."""
import queue
import time
import random
import logging

from src.messages import EventMessage

VALID_RANGE = {
    "temperature": (-20.0, 60.0),
    "humidity":    (0.0, 100.0),
    "luminosity":  (0.0, 2000.0),
}


def burst_producer(q: queue.Queue, name: str,
                   bursts: int = 5, burst_size: int = 30,
                   pause: float = 0.5) -> None:
    """Produit des rafales de messages IoT vers la queue principale.

    Chaque burst génère burst_size messages rapidement, puis attend pause secondes.
    10 % des messages ont une valeur invalide (-999) pour tester le retry/DLQ.

    Args:
        q:          Queue principale (bornée → backpressure).
        name:       Nom du producteur (pour les logs).
        bursts:     Nombre de rafales.
        burst_size: Messages par rafale.
        pause:      Pause entre rafales (secondes).
    """
    sensors = [f"sensor-{name[-1]}{i}" for i in range(1, 4)]
    metrics_list = list(VALID_RANGE.keys())
    produced = 0
    dropped  = 0

    for b in range(bursts):
        for _ in range(burst_size):
            metric = random.choice(metrics_list)

            # 10 % de valeurs invalides pour tester le circuit retry/DLQ
            if random.random() < 0.1:
                value = -999.0
            else:
                lo, hi = VALID_RANGE[metric]
                value = round(random.uniform(lo, hi), 2)

            msg = EventMessage(
                msg_type="sensor_reading",
                payload={
                    "sensor_id": random.choice(sensors),
                    "metric":    metric,
                    "value":     value,
                },
            )
            try:
                q.put(msg, timeout=2)
                produced += 1
            except queue.Full:
                dropped += 1
                logging.warning(
                    "[%s] Queue PLEINE — drop %s (backpressure)",
                    name, msg.msg_id[:8]
                )
            time.sleep(random.uniform(0.005, 0.015))

        logging.info("[%s] Burst %d/%d terminé (produit=%d, droppé=%d)",
                     name, b + 1, bursts, produced, dropped)
        time.sleep(pause)

    logging.info("[%s] Terminé : %d produits, %d droppés",
                 name, produced, dropped)
