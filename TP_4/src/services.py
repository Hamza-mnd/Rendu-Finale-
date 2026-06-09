"""services.py — Logique métier : ingest.batch, stats, health (Séance 4)."""
import threading
import time
import csv
import os
import statistics

from src.models import SensorReading

MAX_BATCH_SIZE = 1000


class DataStore:
    """Stockage thread-safe des lectures capteur en mémoire."""

    def __init__(self):
        self._readings: list[dict] = []
        self._lock = threading.Lock()

    def add_readings(self, readings: list[dict]) -> int:
        """Ajoute des lectures. Retourne le total stocké."""
        with self._lock:
            self._readings.extend(readings)
            return len(self._readings)

    def get_all(self) -> list[dict]:
        """Retourne une copie de toutes les lectures."""
        with self._lock:
            return list(self._readings)

    def get_by_date(self, date_str: str) -> list[dict]:
        """Retourne les lectures dont ts commence par date_str."""
        with self._lock:
            return [r for r in self._readings if r["ts"].startswith(date_str)]

    def export_csv(self, filepath: str) -> int:
        """Exporte toutes les lectures en CSV. Retourne le nombre de lignes."""
        with self._lock:
            data = list(self._readings)
        if not data:
            return 0
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["sensor_id", "ts", "value"])
            writer.writeheader()
            writer.writerows(data)
        return len(data)


# Instance globale partagée par tous les threads
store = DataStore()


# ============================================================
# MÉTHODES RPC
# ============================================================

def health_ping(params: dict) -> dict:
    """Méthode RPC : health.ping — vérification de disponibilité."""
    return {"status": "ok", "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}


def ingest_batch(params: dict) -> dict:
    """Méthode RPC : ingest.batch — ingestion d'un lot de lectures.

    Params : {"readings": [{sensor_id, ts, value}, ...]}
    Result : {"accepted": N, "rejected": M, "errors": [...]}
    """
    readings_raw = params.get("readings")
    if readings_raw is None:
        raise ValueError("Paramètre obligatoire manquant : 'readings'")
    if not isinstance(readings_raw, list):
        raise ValueError("Le paramètre 'readings' doit être une liste")
    if len(readings_raw) > MAX_BATCH_SIZE:
        raise OverflowError(
            f"Batch trop volumineux : {len(readings_raw)} > {MAX_BATCH_SIZE}"
        )

    accepted = []
    rejected = []

    for i, raw in enumerate(readings_raw):
        if not isinstance(raw, dict):
            rejected.append({"index": i, "error": "Not a JSON object"})
            continue

        try:
            reading = SensorReading(
                sensor_id=raw.get("sensor_id", ""),
                ts=raw.get("ts", ""),
                value=raw.get("value"),
            )
        except (TypeError, KeyError) as e:
            rejected.append({"index": i, "error": str(e)})
            continue

        errors = reading.validate()
        if errors:
            rejected.append({
                "index": i,
                "sensor_id": reading.sensor_id,
                "errors": errors,
            })
        else:
            accepted.append({
                "sensor_id": reading.sensor_id,
                "ts": reading.ts,
                "value": float(reading.value),
            })

    if accepted:
        store.add_readings(accepted)

    return {
        "accepted": len(accepted),
        "rejected": len(rejected),
        "errors": rejected,
    }


def stats_daily_summary(params: dict) -> dict:
    """Méthode RPC : stats.daily_summary — résumé statistique par date.

    Params : {"date": "YYYY-MM-DD"}
    Result : {"date": ..., "count": N, "avg": X, "min": Y, "max": Z}
    """
    date_str = params.get("date")
    if not date_str or not isinstance(date_str, str):
        raise ValueError(
            "Paramètre 'date' obligatoire (format YYYY-MM-DD)"
        )

    readings = store.get_by_date(date_str)
    if not readings:
        return {"date": date_str, "count": 0, "avg": None, "min": None, "max": None}

    values = [r["value"] for r in readings]
    return {
        "date": date_str,
        "count": len(values),
        "avg": round(statistics.mean(values), 2),
        "min": min(values),
        "max": max(values),
    }


def stats_top_sensors(params: dict) -> dict:
    """Méthode RPC : stats.top_sensors — top N capteurs par valeur moyenne.

    Params : {"n": 5}
    Result : {"sensors": [{"sensor_id": ..., "avg": X}, ...]}
    """
    n = params.get("n", 5)
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("Le paramètre 'n' doit être un entier positif")

    all_readings = store.get_all()
    if not all_readings:
        return {"sensors": []}

    # Grouper par sensor_id
    by_sensor: dict[str, list[float]] = {}
    for r in all_readings:
        by_sensor.setdefault(r["sensor_id"], []).append(r["value"])

    # Calculer la moyenne et trier décroissant
    averages = [
        {"sensor_id": sid, "avg": round(statistics.mean(vals), 2)}
        for sid, vals in by_sensor.items()
    ]
    averages.sort(key=lambda x: x["avg"], reverse=True)

    return {"sensors": averages[:n]}
