# src/events.py
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid


@dataclass
class Event:
    event_id: str
    sensor_id: str
    site_id: str
    event_time: str
    temperature_c: float
    humidity_pct: float

    def partition_key(self, field: str) -> str:
        """Retourne la valeur du champ utilisé comme clé de partition."""
        return str(getattr(self, field))

    def to_dict(self) -> dict:
        return asdict(self)


def make_random_event(sensor_id: str, site_id: str) -> "Event":
    import random
    return Event(
        event_id=f"e-{uuid.uuid4().hex[:8]}",
        sensor_id=sensor_id,
        site_id=site_id,
        event_time=datetime.utcnow().isoformat(timespec="seconds"),
        temperature_c=round(20 + random.uniform(-2, 8), 2),
        humidity_pct=round(55 + random.uniform(-10, 10), 2),
    )


if __name__ == "__main__":
    for sensor, site in [("sensor-01", "SITE-01"), ("sensor-HOT-01", "SITE-02"), ("sensor-03", "SITE-03")]:
        evt = make_random_event(sensor, site)
        print(f"event_id={evt.event_id}  partition_key(sensor_id)={evt.partition_key('sensor_id')}  partition_key(site_id)={evt.partition_key('site_id')}")
