"""Application unifiée de la plateforme de livraison."""

import threading
import time
import os
import sys

from broker import MiniBroker
from producers import EventProducer
from consumers import ConsumerA, ConsumerB
from service import OrderService
from dashboard import Dashboard


class DeliveryPlatform:
    """Plateforme complète de suivi de commandes."""
    
    def __init__(self, num_partitions: int = 4):
        self.num_partitions = num_partitions
        self.broker = None
        self.producer = None
        self.consumer_a = None
        self.consumer_b = None
        self.order_service = None
        self.dashboard = None
        self.running = False
        
    def start(self):
        """Démarre tous les composants."""
        print("=" * 60)
        print("📦 Démarrage de la plateforme de livraison...")
        print("=" * 60)
        
        # Création des répertoires - avec gestion d'erreur
        directories = ["broker_data", "offsets", "data"]
        for dir_name in directories:
            try:
                if not os.path.exists(dir_name):
                    os.makedirs(dir_name)
                    print(f"✓ Créé dossier: {dir_name}")
                else:
                    print(f"✓ Dossier existant: {dir_name}")
            except Exception as e:
                print(f"⚠️ Avertissement pour {dir_name}: {e}")
        
        try:
            # 1. Broker
            print("✓ Initialisation du broker...")
            self.broker = MiniBroker(num_partitions=self.num_partitions, data_dir="broker_data")
            
            # 2. Producteur
            print("✓ Initialisation du producteur...")
            self.producer = EventProducer(self.broker)
            
            # 3. Consumers
            print("✓ Initialisation des consumers...")
            partitions_a = {p for p in range(self.num_partitions) if p % 2 == 0}
            partitions_b = {p for p in range(self.num_partitions) if p % 2 == 1}
            
            self.consumer_a = ConsumerA("consumer_a", self.broker, partitions=partitions_a)
            self.consumer_b = ConsumerB("consumer_b", self.broker, partitions=partitions_b)
            
            # 4. Service de commandes
            print("✓ Démarrage du service de commandes...")
            self.order_service = OrderService(producer=self.producer)
            
            # 5. Dashboard (mode texte)
            self.dashboard = Dashboard(self.consumer_a, self.consumer_b, self.broker, update_interval=5)
            
            # Démarrage
            self.running = True
            self.consumer_a.start()
            self.consumer_b.start()
            
            service_thread = threading.Thread(target=self.order_service.start)
            service_thread.daemon = True
            service_thread.start()
            
            self.dashboard.start()
            
            print("\n✅ PLATEFORME PRÊTE!")
            print("=" * 60)
            print("📡 Service API: localhost:9999")
            print("📊 Dashboard: mis à jour automatiquement")
            print("🤖 Assistant IA: interface graphique")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Erreur lors du démarrage: {e}")
            self.stop()
            raise
    
    def stop(self):
        """Arrête tous les composants."""
        print("\n🛑 Arrêt de la plateforme...")
        self.running = False
        
        if self.consumer_a:
            try:
                self.consumer_a.stop()
            except:
                pass
        if self.consumer_b:
            try:
                self.consumer_b.stop()
            except:
                pass
        if self.order_service:
            try:
                self.order_service.stop()
            except:
                pass
        if self.dashboard:
            try:
                self.dashboard.stop()
            except:
                pass
        
        print("✅ Plateforme arrêtée")
    
    def send_test_orders(self):
        """Envoie des commandes de test."""
        test_orders = [
            {'customer_id': 'CUST-001', 'city': 'Fes', 'zone': 'Saiss', 'courier_id': 'CRR-01', 'amount': 245.00, 'items_count': 2},
            {'customer_id': 'CUST-002', 'city': 'Casablanca', 'zone': 'Maarif', 'courier_id': 'CRR-02', 'amount': 890.50, 'items_count': 5},
            {'customer_id': 'CUST-003', 'city': 'Rabat', 'zone': 'Agdal', 'courier_id': 'CRR-03', 'amount': 120.00, 'items_count': 1},
            {'customer_id': 'CUST-004', 'city': 'Marrakech', 'zone': 'Guéliz', 'courier_id': 'CRR-04', 'amount': 550.00, 'items_count': 3},
            {'customer_id': 'CUST-005', 'city': 'Tanger', 'zone': 'Centre', 'courier_id': 'CRR-05', 'amount': 175.00, 'items_count': 1},
        ]
        
        print("\n📦 Envoi des commandes de test...")
        for i, order in enumerate(test_orders, 1):
            try:
                response = self.order_service.send_order(order)
                if response.get('success'):
                    order_id = response.get('order_id')
                    print(f"   ✓ Commande #{i} créée: {order_id}")
                    
                    # Simuler le cycle de vie
                    time.sleep(0.3)
                    self.producer.publish_order_confirmed(order_id, order['city'], courier_id=order['courier_id'])
                    time.sleep(0.3)
                    self.producer.publish_order_prepared(order_id, order['city'], courier_id=order['courier_id'])
                    time.sleep(0.3)
                    self.producer.publish_order_dispatched(order_id, order['city'], courier_id=order['courier_id'])
                    time.sleep(0.3)
                    
                    if i <= 3:
                        self.producer.publish_order_delivered(order_id, order['city'], courier_id=order['courier_id'], amount=order['amount'])
                        print(f"   ✓ Commande #{i} livrée!")
                    else:
                        self.producer.publish_delivery_failed(order_id, order['city'], "Adresse incorrecte", courier_id=order['courier_id'])
                        print(f"   ✗ Commande #{i} échouée")
                else:
                    print(f"   ✗ Commande #{i} échouée: {response.get('error')}")
            except Exception as e:
                print(f"   ✗ Erreur commande #{i}: {e}")
            
            time.sleep(0.2)
    
    def interactive_mode(self):
        """Mode interactif en ligne de commande."""
        print("\n🎮 MODE INTERACTIF")
        print("-" * 40)
        print("Commandes disponibles:")
        print("  1 - Envoyer commandes test")
        print("  2 - Voir statistiques")
        print("  3 - Vérifier statut commande")
        print("  4 - Exporter rapport")
        print("  q - Quitter")
        
        while self.running:
            try:
                cmd = input("\n> ").strip().lower()
                
                if cmd == '1':
                    self.send_test_orders()
                elif cmd == '2':
                    if self.consumer_a:
                        stats = self.consumer_a.get_stats()
                        print(f"\n📊 Statistiques:")
                        print(f"  Commandes: {stats['total_created']}")
                        print(f"  Livrées: {stats['total_delivered']}")
                        print(f"  Échecs: {stats['total_failed']}")
                        print(f"  Taux succès: {stats['success_rate']:.1f}%")
                elif cmd == '3':
                    order_id = input("ID commande: ").strip()
                    status = self.consumer_b.get_order_status(order_id) if self.consumer_b else None
                    if status:
                        print(f"  Statut: {status}")
                    else:
                        print("  Commande non trouvée")
                elif cmd == '4':
                    self.dashboard.export_report("rapport_interactif.json")
                elif cmd == 'q':
                    break
                else:
                    print("  Commande non reconnue")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"  Erreur: {e}")