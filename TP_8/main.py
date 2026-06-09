# main.py — Plateforme distribuée de suivi de commandes — Séance 8
"""
Lancement :
    python main.py

Options configurables en tête de fichier :
    NUM_PARTITIONS, NUM_CONSUMERS, SIMULATION_DURATION_S
"""
import logging, threading, time, random
from pathlib import Path

from broker.mini_broker   import MiniBroker, partition_of
from contracts.order      import validate_order
from service.order_service import OrderService
from producers.event_producer import EventProducer
from consumers.consumer_a import ConsumerA
from consumers.consumer_b import ConsumerB
from offsets.offset_store import OffsetStore
from storage.partitioned_store import PartitionedStore
from dashboard.dashboard  import Dashboard

# ── Config ────────────────────────────────────────────────────────────────────
NUM_PARTITIONS       = 4
SIMULATION_DURATION_S = 30
COMMIT_EVERY         = 5
DASHBOARD_REFRESH_S  = 8

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

# Données de simulation
ORDERS_DATA = [
    {"customer_id": "CUST-101", "city": "Fes",        "zone": "Saiss",   "courier_id": "CRR-07", "amount": 245.0,  "items_count": 2},
    {"customer_id": "CUST-204", "city": "Casablanca",  "zone": "Maarif",  "courier_id": "CRR-12", "amount": 890.5,  "items_count": 5},
    {"customer_id": "CUST-315", "city": "Rabat",       "zone": "Agdal",   "courier_id": "CRR-03", "amount": 120.0,  "items_count": 1},
    {"customer_id": "CUST-417", "city": "Fes",         "zone": "Narjiss", "courier_id": "CRR-07", "amount": 550.0,  "items_count": 3},
    {"customer_id": "CUST-523", "city": "Marrakech",   "zone": "Gueliz",  "courier_id": "CRR-19", "amount": 175.0,  "items_count": 1},
    {"customer_id": "CUST-601", "city": "Tanger",      "zone": "Centre",  "courier_id": "CRR-05", "amount": 310.0,  "items_count": 2},
    {"customer_id": "CUST-702", "city": "Casablanca",  "zone": "Anfa",    "courier_id": "CRR-12", "amount": 430.0,  "items_count": 4},
    {"customer_id": "CUST-808", "city": "Rabat",       "zone": "Hay Riad","courier_id": "CRR-03", "amount": 95.0,   "items_count": 1},
    # Invalides (tests de rejet)
    {"customer_id": "CUST-999", "city": "InvalidCity", "zone": "X",       "courier_id": "CRR-00", "amount": 100.0,  "items_count": 1},
    {"customer_id": "CUST-998", "city": "Fes",         "zone": "Y",       "courier_id": "CRR-07", "amount": -50.0,  "items_count": 1},
]


def main():
    log.info("=== Démarrage Séance 8 — Plateforme livraison ===")

    broker     = MiniBroker(NUM_PARTITIONS)
    offsets_a  = OffsetStore("offsets/offsets_a.json")
    offsets_b  = OffsetStore("offsets/offsets_b.json")
    storage    = PartitionedStore("data")
    service    = OrderService(broker)
    producer   = EventProducer(broker)
    stop_event = threading.Event()

    # Assignation round-robin des partitions (2 consumers × 2 partitions chacun)
    all_partitions = list(range(NUM_PARTITIONS))
    partitions_a = [p for p in all_partitions if p % 2 == 0]   # [0, 2]
    partitions_b = [p for p in all_partitions if p % 2 == 1]   # [1, 3]

    consumer_a = ConsumerA(partitions_a, broker, offsets_a, storage, stop_event, COMMIT_EVERY)
    consumer_b = ConsumerB(partitions_b, broker, offsets_b, storage, stop_event, COMMIT_EVERY)
    dashboard  = Dashboard(consumer_a, consumer_b, broker, offsets_a, offsets_b,
                           DASHBOARD_REFRESH_S, stop_event)

    consumer_a.start()
    consumer_b.start()
    dash_thread = threading.Thread(target=dashboard.run, daemon=True, name="dashboard")
    dash_thread.start()

    log.info("Partitions A=%s B=%s", partitions_a, partitions_b)

    # ── Phase 1 : réception synchrone de commandes via OrderService ──────────
    log.info("--- Phase 1 : prise de commandes ---")
    created_orders = []
    for data in ORDERS_DATA:
        result = service.create_order(data)
        if result["status"] == "accepted":
            created_orders.append((data, result["order_id"]))
        time.sleep(0.05)

    # ── Phase 2 : simulation du cycle de vie complet ──────────────────────────
    log.info("--- Phase 2 : simulation des cycles de vie ---")
    for data, order_id in created_orders[:6]:   # 6 commandes complètes
        outcome = random.choice(["delivered", "failed", "cancelled"])
        if outcome == "delivered":
            producer.simulate_lifecycle(order_id, data["city"], data["zone"],
                                        data["courier_id"], data["amount"], delay_s=0.05)
        elif outcome == "failed":
            producer.publish("order_dispatched", order_id, data["city"], data["zone"],
                             data["courier_id"], data["amount"], "dispatched")
            producer.publish("delivery_failed",  order_id, data["city"], data["zone"],
                             data["courier_id"], data["amount"], "failed")
        else:
            producer.publish("order_cancelled", order_id, data["city"], data["zone"],
                             data["courier_id"], data["amount"], "cancelled")
        time.sleep(0.1)

    # ── Attente de traitement ─────────────────────────────────────────────────
    log.info("Pipeline en cours — attente %ds…", SIMULATION_DURATION_S)
    try:
        time.sleep(SIMULATION_DURATION_S)
    except KeyboardInterrupt:
        log.warning("Interruption clavier — arrêt propre…")
    finally:
        stop_event.set()
        consumer_a.join(timeout=3)
        consumer_b.join(timeout=3)
        dashboard.export_report("rapport_final.json")
        log.info("Broker final : %s", broker.summary())
        log.info("Offsets A : %s", offsets_a.all())
        log.info("Offsets B : %s", offsets_b.all())
        log.info("=== Pipeline arrêté ===")


if __name__ == "__main__":
    main()
