# src/main.py
"""
Orchestrateur du mini broker partitionné — Séance 7.

Usage :
    python -m src.main [OPTIONS]

Options :
    --partitions      Nombre de partitions           (défaut : 4)
    --consumers       Nombre de consumers            (défaut : 2)
    --key-field       Champ clé de partition         (défaut : sensor_id)
    --producer-rate   Délai producteur en ms         (défaut : 50)
    --consumer-delay  Délai traitement consumer en ms(défaut : 30)
    --commit-every    Fréquence commit (nb messages) (défaut : 5)
    --duration        Durée d'exécution en secondes  (défaut : 30)
    --group           Nom du consumer group          (défaut : agri-stats)
"""
import argparse
import logging
import random
import threading
import time
from pathlib import Path

from .broker import Broker
from .consumers import Consumer, assign
from .events import make_random_event
from .metrics import Metrics
from .offsets import OffsetStore
from .storage import Storage

# ── Logging ──────────────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
    handlers=[
        logging.FileHandler("logs/run.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("main")

# ── Jeu de données simulé ─────────────────────────────────────────────────────
# sensor-HOT-01 est volontairement sur-représenté pour observer le skew
SENSORS = [f"sensor-{i:02d}" for i in range(1, 11)] + ["sensor-HOT-01"] * 5
SITES = ["SITE-01", "SITE-02", "SITE-03", "SITE-04"]


# ── Producteur ────────────────────────────────────────────────────────────────
def producer_loop(broker: Broker, stop_event: threading.Event, rate_ms: int) -> None:
    """Génère des événements IoT aléatoires et les publie dans le broker."""
    while not stop_event.is_set():
        evt = make_random_event(random.choice(SENSORS), random.choice(SITES))
        p = broker.publish(evt)
        log.debug("publié %s → partition %d", evt.event_id, p)
        time.sleep(rate_ms / 1000)


# ── Argparse ──────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mini broker partitionné — Séance 7")
    p.add_argument("--partitions",     type=int, default=4,           help="Nombre de partitions")
    p.add_argument("--consumers",      type=int, default=2,           help="Nombre de consumers")
    p.add_argument("--key-field",      default="sensor_id",           help="Champ clé de partition")
    p.add_argument("--producer-rate",  type=int, default=50,          help="Délai producteur (ms)")
    p.add_argument("--consumer-delay", type=int, default=30,          help="Délai traitement (ms)")
    p.add_argument("--commit-every",   type=int, default=5,           help="Fréquence commit")
    p.add_argument("--duration",       type=int, default=30,          help="Durée (secondes)")
    p.add_argument("--group",          default="agri-stats",          help="Nom du consumer group")
    return p.parse_args()


# ── Point d'entrée ────────────────────────────────────────────────────────────
def main() -> None:
    args = parse_args()

    log.info("=== Démarrage pipeline Séance 7 ===")
    log.info("Partitions=%d | Consumers=%d | key_field=%s | groupe=%s",
             args.partitions, args.consumers, args.key_field, args.group)

    # Initialisation des composants
    broker  = Broker(args.partitions, args.key_field)
    offsets = OffsetStore("state/offsets.json")
    storage = Storage("outputs")
    metrics = Metrics(broker, offsets, args.group)

    # Assignation des partitions aux consumers
    consumer_ids = [f"C{i}" for i in range(args.consumers)]
    assignment = assign(args.partitions, consumer_ids)
    log.info("Assignation : %s", assignment)

    stop_event = threading.Event()

    # Démarrage des consumers
    consumers: list[Consumer] = []
    for cid in consumer_ids:
        c = Consumer(
            cid, assignment[cid], broker, offsets, storage, metrics,
            args.group, args.consumer_delay, args.commit_every, stop_event,
        )
        c.start()
        consumers.append(c)

    # Démarrage du producteur
    prod_thread = threading.Thread(
        target=producer_loop,
        args=(broker, stop_event, args.producer_rate),
        daemon=True,
        name="producer",
    )
    prod_thread.start()

    # Boucle principale : affichage des métriques toutes les 2 s
    t0 = time.time()
    try:
        while time.time() - t0 < args.duration:
            time.sleep(2)
            snap = metrics.snapshot()
            log.info("[métriques] lag=%d | backlog=%s | throughput=%s",
                     snap["total_lag"],
                     snap["backlog_by_partition"],
                     snap["throughput_per_consumer"])
    except KeyboardInterrupt:
        log.warning("Interruption clavier — arrêt propre en cours…")
    finally:
        stop_event.set()
        for c in consumers:
            c.join(timeout=3)
        prod_thread.join(timeout=2)
        log.info("Offsets finaux : %s", offsets.all_offsets())
        log.info("Partitions broker : %s", broker.summary())
        log.info("=== Pipeline arrêté ===")


if __name__ == "__main__":
    main()
