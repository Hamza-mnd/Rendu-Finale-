# storage/partitioned_store.py
import json, threading
from datetime import datetime
from pathlib import Path
from contracts.event import OrderEvent


class PartitionedStore:
    """
    Stockage JSONL partitionné sur disque.
    Structure : data/city=<ville>/events.jsonl
    Chaque ligne inclut un write_time pour la traçabilité.
    """

    def __init__(self, base: str = "data"):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, evt: OrderEvent, partition: int) -> Path:
        city = evt.city
        target_dir = self.base / f"city={city}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "events.jsonl"
        record = evt.to_dict()
        record["write_time"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        record["partition"] = partition
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with target_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return target_file

    def read_partition(self, city: str) -> list[dict]:
        """Relit tous les événements d'une ville (utile pour reconstruction d'historique)."""
        target_file = self.base / f"city={city}" / "events.jsonl"
        if not target_file.exists():
            return []
        records = []
        with target_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
