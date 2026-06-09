"""workers.py — Validation et traitement des messages IoT (Séance 5)."""
import queue
import time
import logging
import threading

from src.messages import EventMessage

VALID_RANGE = {
    "temperature": (-20.0, 60.0),
    "humidity":    (0.0, 100.0),
    "luminosity":  (0.0, 2000.0),
}


def validate(msg: EventMessage) -> bool:
    """Vérifie que la valeur du capteur est dans la plage attendue.

    Returns:
        True si la lecture est valide, False sinon.
    """
    metric = msg.payload.get("metric", "")
    value  = msg.payload.get("value")

    if metric not in VALID_RANGE or value is None:
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False

    lo, hi = VALID_RANGE[metric]
    return lo <= numeric <= hi


def worker_loop(main_q: queue.Queue, dlq: queue.Queue,
                storage, metrics, stop: threading.Event,
                name: str) -> None:
    """Boucle principale du worker : get → validate → store ou retry/DLQ.

    Stratégie :
      - Validation OK  → écriture CSV + compteur succès.
      - Validation KO + should_retry() → remise en queue (retry).
      - Validation KO + épuisé        → dead-letter queue.

    Args:
        main_q:  Queue principale des messages à traiter.
        dlq:     Dead-letter queue pour les échecs définitifs.
        storage: CSVStorage thread-safe.
        metrics: PipelineMetrics thread-safe.
        stop:    Event de signalement d'arrêt.
        name:    Nom du worker (pour les logs).
    """
    while not stop.is_set():
        try:
            msg = main_q.get(timeout=1)
        except queue.Empty:
            continue

        msg.attempts += 1

        if validate(msg):
            latency = time.time() - msg.created_at
            storage.write(msg)
            metrics.record_success(latency)
            logging.debug("[%s] OK %s | lat=%.3fs | val=%s",
                          name, msg.msg_id[:8], latency,
                          msg.payload.get("value"))
        else:
            if msg.should_retry():
                # Retry : remise en queue principale
                try:
                    main_q.put(msg, timeout=1)
                    metrics.record_retry()
                    logging.info("[%s] Retry #%d %s | val=%s",
                                 name, msg.attempts, msg.msg_id[:8],
                                 msg.payload.get("value"))
                except queue.Full:
                    # Queue pleine au moment du retry → DLQ directement
                    dlq.put(msg)
                    metrics.record_failure()
                    logging.warning("[%s] Retry impossible (queue pleine) → DLQ %s",
                                    name, msg.msg_id[:8])
            else:
                # Épuisé → dead-letter queue
                dlq.put(msg)
                metrics.record_failure()
                logging.warning("[%s] DLQ %s après %d tentatives",
                                name, msg.msg_id[:8], msg.attempts)

        main_q.task_done()
