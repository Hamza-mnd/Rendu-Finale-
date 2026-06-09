"""Stockage partitionné sur disque."""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import threading


class PartitionedStore:
    """Stockage partitionné basé sur la ville."""
    
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.lock = threading.RLock()
        os.makedirs(base_dir, exist_ok=True)
    
    def _get_city_dir(self, city: str) -> str:
        city_dir = os.path.join(self.base_dir, f"city={city}")
        os.makedirs(city_dir, exist_ok=True)
        return city_dir
    
    def _get_events_file(self, city: str) -> str:
        return os.path.join(self._get_city_dir(city), "events.jsonl")
    
    def write_event(self, city: str, event: Dict[str, Any]):
        with self.lock:
            filepath = self._get_events_file(city)
            with open(filepath, 'a', encoding='utf-8') as f:
                record = {
                    'event': event,
                    'storage_metadata': {
                        'write_timestamp': datetime.now().isoformat(),
                        'city': city
                    }
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    def read_city_events(self, city: str) -> List[Dict[str, Any]]:
        filepath = self._get_events_file(city)
        events = []
        
        if not os.path.exists(filepath):
            return events
        
        with self.lock:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            events.append(record)
                        except json.JSONDecodeError:
                            continue
        
        return events
    
    def read_all_events(self) -> Dict[str, List[Dict[str, Any]]]:
        all_events = {}
        
        if not os.path.exists(self.base_dir):
            return all_events
        
        for item in os.listdir(self.base_dir):
            if item.startswith('city=') and os.path.isdir(os.path.join(self.base_dir, item)):
                city = item.split('=')[1]
                all_events[city] = self.read_city_events(city)
        
        return all_events