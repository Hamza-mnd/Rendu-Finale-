"""storage.py — Écriture CSV thread-safe + agrégation (Séance 5)."""
import csv
import threading
import statistics
import os
from collections import defaultdict

from src.messages import EventMessage


class CSVStorage:
    """Stockage thread-safe des lectures valides en CSV + mémoire.

    Args:
        path: Chemin du fichier CSV de sortie.
    """

    def __init__(self, path: str = "outputs/valid_readings.csv"):
        self.path    = path
        self._lock   = threading.Lock()
        self._records: list[dict] = []

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["msg_id", "sensor_id", "metric", "value", "timestamp"])

    def write(self, msg: EventMessage) -> None:
        """Écrit une lecture valide dans le CSV et en mémoire."""
        row = {
            "msg_id":    msg.msg_id[:8],
            "sensor_id": msg.payload["sensor_id"],
            "metric":    msg.payload["metric"],
            "value":     msg.payload["value"],
            "timestamp": msg.created_at,
        }
        with self._lock:
            self._records.append(row)
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row.values())

    def aggregate(self) -> dict:
        """Calcule count, mean, min, max par capteur.

        Returns:
            Dict {sensor_id: {count, mean, min, max}}
        """
        by_sensor: dict[str, list[float]] = defaultdict(list)
        with self._lock:
            for r in self._records:
                by_sensor[r["sensor_id"]].append(float(r["value"]))

        summary = {}
        for sid, vals in by_sensor.items():
            summary[sid] = {
                "count": len(vals),
                "mean":  round(statistics.mean(vals), 2),
                "min":   round(min(vals), 2),
                "max":   round(max(vals), 2),
            }
        return summary

    def count(self) -> int:
        """Retourne le nombre de lectures stockées."""
        with self._lock:
            return len(self._records)
