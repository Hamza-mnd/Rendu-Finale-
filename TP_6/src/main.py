"""main.py — Point d'entrée du pipeline streaming IoT (Séance 6).

Usage (depuis la racine du projet) :
    python src/main.py
    python -m src.main
"""
import sys
import os
# Permet le lancement direct : python src/main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import queue
import time
import json
import logging
import pathlib

from src.events import Event
from src.source import EventSource
from src.processor import StreamProcessor
from src.checkpoint import save_checkpoint, load_checkpoint
from src.sink import export_aggregates_csv, export_json, generate_run_report
from src.metrics import Metrics

# ============================================================
# CONFIGURATION
# ============================================================
WINDOW_SIZE          = 60     # secondes (fenêtre tumbling)
ALLOWED_LATENESS     = 120    # secondes de tolérance après fermeture
CHECKPOINT_INTERVAL  = 10     # secondes entre checkpoints
QUEUE_MAXSIZE        = 50
WATERMARK_MARGIN     = 5.0    # secondes
EVENTS_FILE          = "data/events.json"
CHECKPOINT_PATH      = "checkpoints/state.json"
SOURCE_DELAY         = 0.2    # délai entre événements (simule le flux)


def setup_logging():
    """Configure le logging : fichier + console simultanément."""
    pathlib.Path("logs").mkdir(exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler("logs/pipeline.log", mode="w", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main():
    setup_logging()
    logger = logging.getLogger("main")

    # Créer dossiers
    for d in ["outputs", "logs", "checkpoints", "data"]:
        pathlib.Path(d).mkdir(exist_ok=True)

    # ---- Charger les événements ----
    events_raw = json.loads(pathlib.Path(EVENTS_FILE).read_text(encoding="utf-8"))
    logger.info("Chargement de %d événements depuis %s", len(events_raw), EVENTS_FILE)

    # ---- Initialisation ----
    q         = queue.Queue(maxsize=QUEUE_MAXSIZE)
    processor = StreamProcessor(WINDOW_SIZE, ALLOWED_LATENESS, WATERMARK_MARGIN)
    metrics   = Metrics()

    # ---- Reprise checkpoint ? ----
    load_checkpoint(processor, CHECKPOINT_PATH)

    # ---- Lancer la source ----
    source        = EventSource(events_raw, q, delay=SOURCE_DELAY)
    source_thread = source.start()

    # ---- Boucle principale ----
    last_checkpoint = time.time()
    start_time      = time.time()
    logger.info("Pipeline démarré.")

    while True:
        try:
            raw = q.get(timeout=2.0)
        except queue.Empty:
            if not source_thread.is_alive():
                logger.info("Source terminée et queue vide → arrêt.")
                break
            continue

        if raw is None:
            logger.info("Sentinel reçu → fin du flux.")
            break

        # Traiter l'événement
        event  = Event.from_dict(raw)
        status = processor.process_event(event)
        metrics.record_latency(event.event_time)

        # Flush les fenêtres fermées après chaque événement
        processor.flush_closed_windows()

        # Checkpoint périodique
        if time.time() - last_checkpoint >= CHECKPOINT_INTERVAL:
            save_checkpoint(processor, CHECKPOINT_PATH)
            last_checkpoint = time.time()

        # Dashboard métriques
        metrics.report(processor, q.qsize())

    # ---- Flush final (fenêtres encore ouvertes à la fin du flux) ----
    logger.info("Flush final des fenêtres restantes (%d clés).", len(processor.state))
    for (sid, wk) in list(processor.state.keys()):
        ws = processor.state[(sid, wk)]
        record = {
            "sensor_id":    sid,
            "window_start": wk,
            "window_end":   wk + WINDOW_SIZE,
            **ws.to_dict(),
        }
        processor.flushed_windows.append(record)
    processor.state.clear()

    duration = time.time() - start_time

    # ---- Exports ----
    export_aggregates_csv(processor.flushed_windows, "outputs/aggregates.csv")
    export_json(processor.late_events,    "outputs/late_events.json")
    export_json(processor.dropped_events, "outputs/dropped_events.json")
    generate_run_report(processor, duration, "outputs/run_report.json")
    save_checkpoint(processor, CHECKPOINT_PATH)

    # ---- Résumé final ----
    print("\n" + "=" * 55)
    print("  RÉSULTAT FINAL — Pipeline Streaming IoT")
    print("=" * 55)
    print(f"  Événements traités    : {processor.events_processed}")
    print(f"  Fenêtres flushées     : {len(processor.flushed_windows)}")
    print(f"  Late acceptés         : {len(processor.late_events)}")
    print(f"  Dropped (too-late)    : {len(processor.dropped_events)}")
    print(f"  Durée                 : {round(duration, 2)}s")
    print(f"  Throughput            : {round(processor.events_processed / max(duration, 0.01), 2)} evt/s")
    print("=" * 55)

    # ---- Assertions ----
    assert processor.events_processed == len(events_raw), \
        f"events_processed={processor.events_processed} != {len(events_raw)}"
    assert len(processor.flushed_windows) > 0, "Aucune fenêtre flushée !"
    assert any(e["event_id"] == "evt-011" for e in processor.dropped_events), \
        "evt-011 (09:55) aurait dû être dropped (too-late) !"
    assert len(processor.dropped_events) >= 1, "Au moins 1 événement doit être dropped"
    assert pathlib.Path("outputs/aggregates.csv").exists(), "aggregates.csv manquant"
    assert pathlib.Path("checkpoints/state.json").exists(), "checkpoint manquant"

    print("\n✅ Toutes les assertions passent !")
    logger.info("Pipeline terminé avec succès.")


if __name__ == "__main__":
    main()
