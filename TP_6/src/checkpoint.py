"""checkpoint.py — Sauvegarde et reprise de l'état du processeur (Séance 6)."""
import json
import pathlib
import logging

logger = logging.getLogger(__name__)


def save_checkpoint(processor, path: str) -> None:
    """Sérialise l'état complet du processeur en JSON.

    Convertit les tuples (sensor_id, window_start) en chaînes "sid|wk"
    car JSON ne supporte pas les tuples comme clés.

    Args:
        processor: Instance de StreamProcessor.
        path:      Chemin du fichier checkpoint.
    """
    state_ser = {
        f"{sid}|{wk}": ws.to_dict()
        for (sid, wk), ws in processor.state.items()
    }
    payload = {
        "max_event_time":   processor.max_event_time,
        "events_processed": processor.events_processed,
        "state":            state_ser,
    }
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2))
    logger.info("Checkpoint sauvegardé → %s (%d clés)", path, len(state_ser))


def load_checkpoint(processor, path: str) -> bool:
    """Recharge l'état depuis un fichier checkpoint existant.

    Args:
        processor: Instance de StreamProcessor à restaurer.
        path:      Chemin du fichier checkpoint.

    Returns:
        True si rechargé, False si le fichier n'existe pas.
    """
    from src.processor import WindowState

    p = pathlib.Path(path)
    if not p.exists():
        logger.info("Pas de checkpoint trouvé — démarrage à froid.")
        return False

    data = json.loads(p.read_text())
    processor.max_event_time   = data.get("max_event_time", 0.0)
    processor.events_processed = data.get("events_processed", 0)

    for key_str, ws_dict in data.get("state", {}).items():
        sid, wk_str = key_str.split("|", 1)
        ws = WindowState(
            count=        ws_dict.get("count", 0),
            sum_temp=     ws_dict.get("sum_temp", 0.0),
            sum_humidity= ws_dict.get("sum_humidity", 0.0),
            min_temp=     ws_dict.get("min_temp", float("inf")),
            max_temp=     ws_dict.get("max_temp", float("-inf")),
        )
        processor.state[(sid, int(float(wk_str)))] = ws

    logger.info("Checkpoint chargé ← %s (%d clés)", path, len(processor.state))
    return True
