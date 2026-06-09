"""main.py — Point d'entrée du pipeline asynchrone IoT (Séance 5).

Usage :
    cd TP_5
    python src/main.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import threading
import logging
import time
import json
import queue

from src.messages import EventMessage
from src.producers import burst_producer
from src.workers import worker_loop
from src.metrics import PipelineMetrics, monitor_loop
from src.storage import CSVStorage
from src.pipeline import Pipeline


def main():
    os.makedirs("logs",    exist_ok=True)
    os.makedirs("outputs", exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(threadName)s] %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler("logs/pipeline.log", mode="w", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    pipe    = Pipeline(maxsize=50)
    metrics = PipelineMetrics()
    storage = CSVStorage("outputs/valid_readings.csv")

    def scale_out():
        if not pipe.increment_workers():
            return
        n = pipe._worker_count
        t = threading.Thread(
            target=worker_loop,
            args=(pipe.main_queue, pipe.dead_letter_queue,
                  storage, metrics, pipe.stop_event, f"Worker-{n}"),
            name=f"Worker-{n}", daemon=True,
        )
        t.start()
        pipe.add_thread(t)
        logging.warning("SCALE-OUT: Worker-%d démarré (backlog=%d)",
                        n, pipe.main_queue.qsize())

    N_WORKERS_INIT = 2
    for i in range(1, N_WORKERS_INIT + 1):
        pipe.increment_workers()
        t = threading.Thread(
            target=worker_loop,
            args=(pipe.main_queue, pipe.dead_letter_queue,
                  storage, metrics, pipe.stop_event, f"Worker-{i}"),
            name=f"Worker-{i}", daemon=True,
        )
        t.start()
        pipe.add_thread(t)

    t_mon = threading.Thread(
        target=monitor_loop,
        args=(pipe.main_queue, metrics, pipe.stop_event, 2, scale_out, 40),
        name="Monitor", daemon=True,
    )
    t_mon.start()
    pipe.add_thread(t_mon)

    prod_threads = []
    for i in range(1, 4):
        t = threading.Thread(
            target=burst_producer,
            args=(pipe.main_queue, f"Prod-{i}", 5, 30, 0.5),
            name=f"Prod-{i}",
        )
        t.start()
        prod_threads.append(t)

    for t in prod_threads:
        t.join()
    logging.info("Tous les producteurs ont terminé.")

    pipe.main_queue.join()
    logging.info("Queue principale vidée.")

    pipe.shutdown(timeout=5)

    snap = metrics.snapshot()
    print("\n" + "=" * 55)
    print("  RÉSULTAT FINAL")
    print("=" * 55)
    print(f"  Messages traités avec succès : {snap['success']}")
    print(f"  Messages échoués (DLQ)       : {snap['failures']}")
    print(f"  Retries effectués            : {snap['retries']}")
    print(f"  Débit moyen                  : {snap['rate_per_sec']} msg/s")
    print(f"  Latence moyenne              : {snap['avg_latency_ms']} ms")
    print(f"  Durée totale                 : {snap['elapsed_sec']} s")
    print("=" * 55)

    dead = []
    while not pipe.dead_letter_queue.empty():
        try:
            msg = pipe.dead_letter_queue.get_nowait()
            dead.append(msg.to_dict())
        except queue.Empty:
            break
    with open("outputs/dead_letters.json", "w", encoding="utf-8") as f:
        json.dump(dead, f, indent=2, default=str)
    logging.info("Dead-letters sauvegardés : %d", len(dead))

    agg = storage.aggregate()
    with open("outputs/aggregation.json", "w", encoding="utf-8") as f:
        json.dump(agg, f, indent=2, ensure_ascii=False)
    logging.info("Agrégation exportée : %d capteurs", len(agg))

    assert snap["success"] > 0,   "Aucun message traité !"
    assert storage.count() == snap["success"]
    assert len(agg) > 0
    print("\n✅ Toutes les assertions passent !")
    logging.info("Pipeline terminé.")


if __name__ == "__main__":
    main()
