"""sink.py — Export CSV, JSON et rapport de run (Séance 6)."""
import csv
import json
import pathlib
import logging

logger = logging.getLogger(__name__)


def export_aggregates_csv(records: list[dict], path: str) -> None:
    """Exporte les agrégats de fenêtres flushées en CSV.

    Args:
        records: Liste de dicts (un par fenêtre flushée).
        path:    Chemin du fichier CSV de sortie.
    """
    if not records:
        logger.warning("Aucun agrégat à exporter.")
        return
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    logger.info("Agrégats exportés → %s (%d lignes)", path, len(records))


def export_json(data, path: str) -> None:
    """Exporte des données quelconques en JSON indenté.

    Args:
        data: Objet sérialisable (list, dict…).
        path: Chemin du fichier de sortie.
    """
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info("JSON exporté → %s", path)


def generate_run_report(processor, duration: float, path: str) -> None:
    """Génère un rapport JSON de la session de traitement.

    Champs : events_processed, windows_flushed, late_accepted,
             dropped, duration_seconds, throughput_eps, remaining_state_keys.

    Args:
        processor: Instance de StreamProcessor.
        duration:  Durée totale du pipeline (secondes).
        path:      Chemin du fichier rapport.
    """
    report = {
        "events_processed":     processor.events_processed,
        "windows_flushed":      len(processor.flushed_windows),
        "late_accepted":        len(processor.late_events),
        "dropped":              len(processor.dropped_events),
        "duration_seconds":     round(duration, 2),
        "throughput_eps":       round(
            processor.events_processed / max(duration, 0.01), 2
        ),
        "remaining_state_keys": len(processor.state),
    }
    export_json(report, path)
    logger.info("Rapport run exporté → %s", path)
