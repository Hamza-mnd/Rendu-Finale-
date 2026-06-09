"""Consumer B: Suivi par livreur."""

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


class ConsumerB:
    """Consumer B - Suivi par livreur."""
    
    OFFSET_FILE = "offsets/offsets.json"
    COMMIT_INTERVAL = 5
    COMMIT_TIME_INTERVAL = 10
    
    def __init__(self, consumer_id: str, broker: MiniBroker, partitions: Optional[Set[int]] = None):
        self.consumer_id = consumer_id
        self.broker = broker
        self.partitions = partitions or set(range(broker.num_partitions))
        self.running = False
        self.thread = None
        
        self.courier_stats = defaultdict(lambda: {
            'deliveries': 0,
            'failures': 0,
            'total_amount': 0.0,
            'cities': set()
        })
        
        self.total_deliveries = 0
        self.total_failures = 0
        self.order_status = {}
        
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
            courier_id = event.get('courier_id')
            order_id = event.get('order_id')
            city = event.get('city') or event.get('partition_key')
            amount = event.get('amount', 0)
            
            if order_id:
                self.order_status[order_id] = event_type
            
            if courier_id:
                if event_type == 'order_delivered':
                    self.courier_stats[courier_id]['deliveries'] += 1
                    self.courier_stats[courier_id]['total_amount'] += amount
                    if city:
                        self.courier_stats[courier_id]['cities'].add(city)
                    self.total_deliveries += 1
                    logger.info(f"✅ Livraison réussie: courier={courier_id}, order={order_id}")
                elif event_type == 'delivery_failed':
                    self.courier_stats[courier_id]['failures'] += 1
                    self.total_failures += 1
                    logger.info(f"❌ Livraison échouée: courier={courier_id}, order={order_id}")
            
            self.store.write_event(city or 'unknown', event)
            
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
        logger.info(f"Consumer B démarré sur les partitions {self.partitions}")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self._save_offsets()
    
    def get_courier_stats(self, courier_id: str = None) -> dict:
        if courier_id:
            stats = self.courier_stats.get(courier_id, {})
            stats_copy = stats.copy()
            if 'cities' in stats_copy:
                stats_copy['cities'] = list(stats_copy['cities'])
            stats_copy['success_rate'] = self._get_success_rate(courier_id)
            return stats_copy
        
        return {
            courier: {
                'deliveries': data['deliveries'],
                'failures': data['failures'],
                'total_amount': data['total_amount'],
                'cities': list(data['cities']),
                'success_rate': self._get_success_rate(courier)
            }
            for courier, data in self.courier_stats.items()
        }
    
    def _get_success_rate(self, courier_id: str) -> float:
        stats = self.courier_stats.get(courier_id, {})
        total = stats.get('deliveries', 0) + stats.get('failures', 0)
        if total == 0:
            return 100.0
        return stats.get('deliveries', 0) / total * 100
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        return self.order_status.get(order_id)
    
    def get_all_orders_status(self) -> Dict[str, str]:
        return self.order_status.copy()