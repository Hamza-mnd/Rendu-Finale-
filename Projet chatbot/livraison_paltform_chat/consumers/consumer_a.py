"""Consumer A: Suivi par statut et par ville."""

import threading
import time
import json
import os
import logging
from typing import Dict, Set, Optional
from collections import defaultdict

from broker import MiniBroker
from storage import PartitionedStore


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConsumerA:
    """Consumer A - Suivi par statut et par ville."""
    
    OFFSET_FILE = "offsets/offsets.json"
    COMMIT_INTERVAL = 5
    COMMIT_TIME_INTERVAL = 10
    
    def __init__(self, consumer_id: str, broker: MiniBroker, partitions: Optional[Set[int]] = None):
        self.consumer_id = consumer_id
        self.broker = broker
        self.partitions = partitions or set(range(broker.num_partitions))
        self.running = False
        self.thread = None
        
        self.stats_by_city = defaultdict(lambda: defaultdict(int))
        self.total_created = 0
        self.total_delivered = 0
        self.total_failed = 0
        self.total_cancelled = 0
        
        self.current_offsets = {}
        self.messages_since_commit = 0
        self.last_commit_time = time.time()
        
        # Créer le dossier offsets s'il n'existe pas
        os.makedirs("offsets", exist_ok=True)
        
        self._load_offsets()
        self.store = PartitionedStore("data")
        
    def _load_offsets(self):
        if os.path.exists(self.OFFSET_FILE):
            try:
                with open(self.OFFSET_FILE, 'r', encoding='utf-8') as f:
                    all_offsets = json.load(f)
                    if self.consumer_id in all_offsets:
                        self.current_offsets = all_offsets[self.consumer_id]
                        logger.info(f"Offsets chargés pour {self.consumer_id}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Erreur chargement offsets: {e}")
        
        for p in self.partitions:
            if str(p) not in self.current_offsets:
                self.current_offsets[str(p)] = 0
    
    def _save_offsets(self):
        all_offsets = {}
        if os.path.exists(self.OFFSET_FILE):
            try:
                with open(self.OFFSET_FILE, 'r', encoding='utf-8') as f:
                    all_offsets = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        all_offsets[self.consumer_id] = self.current_offsets
        
        temp_file = self.OFFSET_FILE + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(all_offsets, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, self.OFFSET_FILE)
    
    def _maybe_commit_offsets(self):
        self.messages_since_commit += 1
        now = time.time()
        if (self.messages_since_commit >= self.COMMIT_INTERVAL or 
            now - self.last_commit_time >= self.COMMIT_TIME_INTERVAL):
            self._save_offsets()
            self.messages_since_commit = 0
            self.last_commit_time = now
    
    def _process_event(self, event: dict, partition: int, offset: int):
        try:
            event_type = event.get('event_type')
            city = event.get('partition_key')
            
            if not city:
                return
            
            self.stats_by_city[city][event_type] += 1
            
            if event_type == 'order_created':
                self.total_created += 1
            elif event_type == 'order_delivered':
                self.total_delivered += 1
            elif event_type == 'delivery_failed':
                self.total_failed += 1
            elif event_type == 'order_cancelled':
                self.total_cancelled += 1
            
            self.store.write_event(city, event)
            
            self.current_offsets[str(partition)] = offset + 1
            self._maybe_commit_offsets()
            
        except Exception as e:
            logger.error(f"Erreur traitement événement: {e}")
    
    def _consume_partition(self, partition: int):
        while self.running:
            try:
                current_offset = self.current_offsets.get(str(partition), 0)
                partition_size = self.broker.get_partition_size(partition)
                
                if current_offset < partition_size:
                    messages = self.broker.get_messages_from_offset(partition, current_offset)
                    for i, message in enumerate(messages):
                        if not self.running:
                            break
                        self._process_event(message, partition, current_offset + i)
                else:
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"Erreur sur partition {partition}: {e}")
                time.sleep(1)
    
    def start(self):
        if self.running:
            return
        
        self.running = True
        
        def run():
            threads = []
            for partition in self.partitions:
                t = threading.Thread(target=self._consume_partition, args=(partition,))
                t.daemon = True
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        
        self.thread = threading.Thread(target=run)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Consumer A démarré sur les partitions {self.partitions}")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self._save_offsets()
    
    def get_stats(self) -> dict:
        return {
            'by_city': dict(self.stats_by_city),
            'total_created': self.total_created,
            'total_delivered': self.total_delivered,
            'total_failed': self.total_failed,
            'total_cancelled': self.total_cancelled,
            'success_rate': self.total_delivered / max(1, self.total_created) * 100,
            'backlog': self.total_created - self.total_delivered - self.total_cancelled
        }