# offsets/offset_store.py
import json, threading
from pathlib import Path


class OffsetStore:
    """
    Persistance thread-safe des offsets par groupe et par partition.
    Écriture atomique via write + rename pour éviter la corruption.
    """

    def __init__(self, path: str = "offsets/offsets.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def get(self, group: str, partition: int) -> int:
        return self._data.get(group, {}).get(str(partition), 0)

    def set_memory(self, group: str, partition: int, offset: int) -> None:
        with self._lock:
            self._data.setdefault(group, {})[str(partition)] = offset

    def commit(self, group: str, partition: int, offset: int) -> None:
        with self._lock:
            self._data.setdefault(group, {})[str(partition)] = offset
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            tmp.replace(self.path)

    def flush(self, group: str, partition: int) -> None:
        off = self.get(group, partition)
        self.commit(group, partition, off)

    def all(self) -> dict:
        return dict(self._data)
