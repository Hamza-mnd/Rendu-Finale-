#!/usr/bin/env python3
"""Script simple pour envoyer des commandes de test."""

import socket
import json
import time

def send_order(order_data):
    """Envoie une commande au service."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(('localhost', 9999))
        s.send(json.dumps(order_data).encode())
        response = json.loads(s.recv(4096).decode())
        s.close()
        return response
    except ConnectionRefusedError:
        return {'success': False, 'error': 'Service non démarré. Lancez d\'abord python main.py --cli'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Commandes de test
test_orders = [
    {'customer_id': 'CUST-001', 'city': 'Fes', 'zone': 'Saiss', 'courier_id': 'CRR-01', 'amount': 245.00, 'items_count': 2},
    {'customer_id': 'CUST-002', 'city': 'Casablanca', 'zone': 'Maarif', 'courier_id': 'CRR-02', 'amount': 890.50, 'items_count': 5},
    {'customer_id': 'CUST-003', 'city': 'Rabat', 'zone': 'Agdal', 'courier_id': 'CRR-03', 'amount': 120.00, 'items_count': 1},
    {'customer_id': 'CUST-004', 'city': 'Marrakech', 'zone': 'Guéliz', 'courier_id': 'CRR-04', 'amount': 550.00, 'items_count': 3},
    {'customer_id': 'CUST-005', 'city': 'Tanger', 'zone': 'Centre', 'courier_id': 'CRR-05', 'amount': 175.00, 'items_count': 1},
]

print("📦 Envoi des commandes de test...")
print("-" * 40)

for i, order in enumerate(test_orders, 1):
    response = send_order(order)
    if response.get('success'):
        order_id = response.get('order_id')
        print(f"✓ Commande #{i} créée: {order_id}")
    else:
        print(f"✗ Commande #{i} échouée: {response.get('error')}")
    time.sleep(0.5)

print("\n✅ Terminé! Les commandes ont été envoyées.")
print("📊 Le tableau de bord devrait maintenant afficher les données.")