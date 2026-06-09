"""events.py — Dataclass Event + parsing ISO → epoch (Séance 6)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Event:
    """Représente un événement IoT horodaté avec toutes ses mesures.

    Attributes:
        event_id      : identifiant unique de l'événement.
        sensor_id     : identifiant du capteur source.
        site_id       : identifiant du site géographique.
        event_time    : timestamp epoch (float) — instant de mesure réel.
        temperature_c : température en °C.
        humidity_pct  : humidité relative en %.
        soil_moisture : humidité du sol [0,1], None si invalide ou absent.
    """
    event_id:      str
    sensor_id:     str
    site_id:       str
    event_time:    float          # epoch seconds (event time)
    temperature_c: float
    humidity_pct:  float
    soil_moisture: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        """Parse un dict brut (JSON) en Event.

        Convertit event_time ISO 8601 → epoch float.
        Gère soil_moisture = "N/A" ou None → None.
        """
        et = datetime.fromisoformat(d["event_time"]).timestamp()
        sm = d.get("soil_moisture")
        if sm is None or isinstance(sm, str):
            sm = None
        else:
            try:
                sm = float(sm)
            except (TypeError, ValueError):
                sm = None

        return cls(
            event_id=      d["event_id"],
            sensor_id=     d["sensor_id"],
            site_id=       d["site_id"],
            event_time=    et,
            temperature_c= float(d["temperature_c"]),
            humidity_pct=  float(d["humidity_pct"]),
            soil_moisture= sm,
        )
