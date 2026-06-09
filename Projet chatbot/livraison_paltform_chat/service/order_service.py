"""Service synchrone de réception de commandes."""

import socket
import json
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Tuple

from contracts import Order, OrderValidator, ValidationError, OrderStatus
from producers import EventProducer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderService:
    """Service synchrone de réception de commandes."""
    
    def __init__(self, host: str = 'localhost', port: int = 9999, producer: EventProducer = None):
        self.host = host
        self.port = port
        self.producer = producer
        self.running = False
        self.server_socket = None
        self.order_counter = 0
        self.counter_lock = threading.Lock()
        self.orders = {}
    
    def _generate_order_id(self) -> str:
        with self.counter_lock:
            self.order_counter += 1
            date_str = datetime.now().strftime("%Y%m%d")
            return f"ORD-{date_str}-{self.order_counter:04d}"
    
    def send_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Client utilitaire pour envoyer une commande."""
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_socket.settimeout(10)
            client_socket.connect((self.host, self.port))
            client_socket.send(json.dumps(order_data).encode('utf-8'))
            response_data = client_socket.recv(4096).decode('utf-8')
            return json.loads(response_data)
        except socket.timeout:
            return {'success': False, 'error': 'Timeout de connexion'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            client_socket.close()
    
    def _process_order(self, order_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        try:
            order = OrderValidator.validate(order_data)
            order_id = self._generate_order_id()
            order.order_id = order_id
            
            self.orders[order_id] = {
                'order_id': order_id,
                'customer_id': order.customer_id,
                'city': order.city,
                'zone': order.zone,
                'courier_id': order.courier_id,
                'amount': order.amount,
                'items_count': order.items_count,
                'status': 'created',
                'created_at': order.created_at
            }
            
            logger.info(f"Commande validée: {order_id}")
            
            if self.producer:
                event_data = {
                    'order_id': order_id,
                    'city': order.city,
                    'courier_id': order.courier_id,
                    'amount': order.amount,
                    'items_count': order.items_count,
                    'zone': order.zone,
                    'status': 'created'
                }
                self.producer.publish_order_created(event_data)
            
            return True, {
                'success': True,
                'order_id': order_id,
                'message': 'Commande créée avec succès'
            }
            
        except ValidationError as e:
            logger.warning(f"Validation échouée: {e}")
            return False, {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            return False, {'success': False, 'error': f"Erreur interne: {str(e)}"}
    
    def _handle_client(self, client_socket: socket.socket, address: tuple):
        try:
            client_socket.settimeout(30)
            data = client_socket.recv(4096).decode('utf-8')
            
            if not data:
                response = {'success': False, 'error': 'Aucune donnée reçue'}
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            try:
                order_data = json.loads(data)
            except json.JSONDecodeError as e:
                response = {'success': False, 'error': f'JSON invalide: {str(e)}'}
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            success, response = self._process_order(order_data)
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except socket.timeout:
            response = {'success': False, 'error': 'Timeout de réception'}
            try:
                client_socket.send(json.dumps(response).encode('utf-8'))
            except:
                pass
        except Exception as e:
            logger.error(f"Erreur avec client {address}: {e}")
        finally:
            client_socket.close()
    
    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        
        logger.info(f"Service de commandes démarré sur {self.host}:{self.port}")
        
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    logger.error(f"Erreur d'acceptation: {e}")
    
    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        logger.info("Service de commandes arrêté")
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        return self.orders.get(order_id)
    
    def get_all_orders(self) -> Dict[str, Dict[str, Any]]:
        return self.orders.copy()