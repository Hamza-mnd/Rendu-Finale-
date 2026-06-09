"""Mini broker partitionné simulé en Python pur."""

import threading
import time
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import json
import os


class BrokerError(Exception):
    """Exception levée par le broker."""
    pass


class MiniBroker:
    """
    Broker de messages simulé avec support des partitions.
    
    Implémente un système de file d'attente partitionnée avec:
    - Plusieurs partitions configurables
    - Persistance des messages
    - Suivi des offsets par consumer
    - Opérations thread-safe
    """
    
    def __init__(self, num_partitions: int = 4, data_dir: str = "broker_data"):
        """
        Initialise le broker.
        
        Args:
            num_partitions: Nombre de partitions (par défaut: 4)
            data_dir: Répertoire pour la persistance des messages
        """
        self.num_partitions = num_partitions
        self.data_dir = data_dir
        self.partitions: List[List[Dict[str, Any]]] = [[] for _ in range(num_partitions)]
        self.offsets: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.lock = threading.RLock()
        
        # Création du répertoire de données
        os.makedirs(data_dir, exist_ok=True)
        
        # Chargement des messages persistés
        self._load_persisted_messages()
        
    def _get_partition_file(self, partition: int) -> str:
        """Retourne le chemin du fichier pour une partition."""
        return os.path.join(self.data_dir, f"partition_{partition}.json")
    
    def _load_persisted_messages(self):
        """Charge les messages depuis les fichiers."""
        for p in range(self.num_partitions):
            filepath = self._get_partition_file(p)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.partitions[p] = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Erreur chargement partition {p}: {e}")
                    self.partitions[p] = []
                    
    def _save_partition(self, partition: int):
        """Sauvegarde une partition sur disque."""
        filepath = self._get_partition_file(partition)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.partitions[partition], f, ensure_ascii=False, indent=2)
    
    def get_partition(self, key: str) -> int:
        """
        Détermine la partition pour une clé donnée en utilisant le hash.
        
        Args:
            key: Clé de partitionnement (ex: ville)
            
        Returns:
            int: Numéro de partition
        """
        return hash(key) % self.num_partitions
    
    def publish(self, message: Dict[str, Any], key: str) -> Tuple[int, int]:
        """
        Publie un message dans le broker.
        
        Args:
            message: Message à publier (dictionnaire)
            key: Clé pour le partitionnement
            
        Returns:
            Tuple[int, int]: (partition, offset)
            
        Raises:
            BrokerError: Si le message ne peut pas être publié
        """
        with self.lock:
            try:
                partition = self.get_partition(key)
                offset = len(self.partitions[partition])
                
                # Ajout des métadonnées
                message['_broker_metadata'] = {
                    'partition': partition,
                    'offset': offset,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.partitions[partition].append(message)
                self._save_partition(partition)
                
                return partition, offset
            except Exception as e:
                raise BrokerError(f"Erreur lors de la publication: {e}")
    
    def consume(self, partition: int, consumer_id: str, auto_commit: bool = True) -> Optional[Dict[str, Any]]:
        """
        Consomme un message à partir d'une partition.
        
        Args:
            partition: Numéro de partition
            consumer_id: Identifiant du consumer
            auto_commit: Si True, met à jour l'offset automatiquement
            
        Returns:
            Optional[Dict[str, Any]]: Message suivant ou None
        """
        with self.lock:
            current_offset = self.offsets[consumer_id][partition]
            
            if current_offset >= len(self.partitions[partition]):
                return None
            
            message = self.partitions[partition][current_offset].copy()
            
            if auto_commit:
                self.offsets[consumer_id][partition] = current_offset + 1
                
            return message
    
    def commit_offset(self, consumer_id: str, partition: int, offset: int):
        """Valide explicitement un offset pour un consumer."""
        with self.lock:
            current_offset = self.offsets[consumer_id][partition]
            if offset > current_offset:
                self.offsets[consumer_id][partition] = offset
    
    def get_offset(self, consumer_id: str, partition: int) -> int:
        """Retourne l'offset actuel pour un consumer sur une partition."""
        with self.lock:
            return self.offsets[consumer_id][partition]
    
    def set_offset(self, consumer_id: str, partition: int, offset: int):
        """Définit l'offset pour un consumer sur une partition."""
        with self.lock:
            if 0 <= offset <= len(self.partitions[partition]):
                self.offsets[consumer_id][partition] = offset
            else:
                raise BrokerError(f"Offset invalide: {offset}")
    
    def get_partition_size(self, partition: int) -> int:
        """Retourne le nombre total de messages dans une partition."""
        with self.lock:
            return len(self.partitions[partition])
    
    def get_lag(self, consumer_id: str, partition: int) -> int:
        """Retourne le lag (messages non consommés) pour un consumer sur une partition."""
        with self.lock:
            total = len(self.partitions[partition])
            consumed = self.offsets[consumer_id][partition]
            return max(0, total - consumed)
    
    def get_all_lags(self, consumer_id: str) -> Dict[int, int]:
        """Retourne les lags pour toutes les partitions."""
        with self.lock:
            return {
                p: self.get_lag(consumer_id, p)
                for p in range(self.num_partitions)
            }
    
    def get_messages_from_offset(self, partition: int, offset: int) -> List[Dict[str, Any]]:
        """Retourne tous les messages à partir d'un offset donné."""
        with self.lock:
            if offset >= len(self.partitions[partition]):
                return []
            return self.partitions[partition][offset:].copy()
    
    def search_orders(self, query: str) -> List[Dict[str, Any]]:
        """Recherche des commandes dans toutes les partitions."""
        results = []
        with self.lock:
            for partition_idx, partition in enumerate(self.partitions):
                for msg in partition:
                    if query.lower() in str(msg).lower():
                        results.append(msg)
        return results