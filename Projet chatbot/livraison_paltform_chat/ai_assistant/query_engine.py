"""Moteur de requêtes pour l'assistant IA."""

import json
import re
from typing import Dict, Any, List, Optional


class QueryEngine:
    """
    Moteur de requêtes pour interroger les données de la plateforme.
    Prépare le contexte pour l'assistant IA.
    """
    
    def __init__(self, order_service, consumer_a, consumer_b, broker):
        self.order_service = order_service
        self.consumer_a = consumer_a
        self.consumer_b = consumer_b
        self.broker = broker
    
    def get_order_info(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations détaillées d'une commande."""
        order = self.order_service.get_order(order_id)
        if order:
            status = self.consumer_b.get_order_status(order_id)
            if status:
                order['current_status'] = status
            return order
        
        results = self.broker.search_orders(order_id)
        if results:
            return results[0]
        
        return None
    
    def get_order_status_text(self, order_id: str) -> str:
        """Retourne le statut d'une commande en texte lisible."""
        status = self.consumer_b.get_order_status(order_id)
        if not status:
            order = self.order_service.get_order(order_id)
            if order:
                return "La commande {} a été créée mais n'a pas encore de mise à jour de statut.".format(order_id)
            return "Commande {} non trouvée.".format(order_id)
        
        status_fr = {
            'order_created': 'créée',
            'order_confirmed': 'confirmée',
            'order_prepared': 'préparée',
            'order_dispatched': 'expédiée',
            'order_delivered': 'livrée',
            'order_cancelled': 'annulée',
            'delivery_failed': 'en échec de livraison'
        }
        
        return "La commande {} est {}.".format(order_id, status_fr.get(status, status))
    
    def get_courier_stats_text(self, courier_id: str = None) -> str:
        """Retourne les statistiques d'un livreur."""
        if courier_id:
            stats = self.consumer_b.get_courier_stats(courier_id)
            if stats:
                deliveries = stats.get('deliveries', 0)
                failures = stats.get('failures', 0)
                rate = stats.get('success_rate', 100)
                return "Livreur {}: {} livraisons réussies, {} échecs, taux de succès: {:.1f}%".format(
                    courier_id, deliveries, failures, rate)
            return "Livreur {} non trouvé.".format(courier_id)
        
        all_stats = self.consumer_b.get_courier_stats()
        if not all_stats:
            return "Aucune donnée livreur disponible."
        
        result = "Statistiques des livreurs:\n"
        for cid, stats in all_stats.items():
            result += "  • {}: {} livraisons, taux {:.1f}%\n".format(
                cid, stats['deliveries'], stats['success_rate'])
        return result
    
    def get_global_stats_text(self) -> str:
        """Retourne les statistiques globales."""
        stats = self.consumer_a.get_stats() if self.consumer_a else {}
        
        if not stats:
            return "Aucune statistique disponible."
        
        return (
            "Statistiques globales:\n"
            "  • Commandes créées: {}\n"
            "  • Livraisons réussies: {}\n"
            "  • Livraisons échouées: {}\n"
            "  • Commandes annulées: {}\n"
            "  • Taux de succès: {:.1f}%\n"
            "  • Backlog: {}"
        ).format(
            stats['total_created'],
            stats['total_delivered'],
            stats['total_failed'],
            stats['total_cancelled'],
            stats['success_rate'],
            stats['backlog']
        )
    
    def get_city_stats_text(self, city: str = None) -> str:
        """Retourne les statistiques par ville."""
        if not self.consumer_a:
            return "Aucune donnée disponible."
        
        city_stats = self.consumer_a.stats_by_city
        
        if city:
            if city in city_stats:
                stats = city_stats[city]
                return "Ville {}: {}".format(city, dict(stats))
            return "Aucune donnée pour la ville {}".format(city)
        
        result = "Statistiques par ville:\n"
        for c, stats in city_stats.items():
            total = sum(stats.values())
            delivered = stats.get('order_delivered', 0)
            result += "  • {}: {} commandes, {} livrées\n".format(c, total, delivered)
        return result
    
    def search_orders(self, query: str) -> List[Dict[str, Any]]:
        """Recherche des commandes par terme."""
        return self.broker.search_orders(query)
    
    def get_all_context(self) -> str:
        """Prépare tout le contexte pour l'assistant."""
        context = []
        
        # Statistiques globales
        context.append(self.get_global_stats_text())
        
        # Top villes
        if self.consumer_a:
            city_stats = self.consumer_a.stats_by_city
            if city_stats:
                top_cities = sorted(city_stats.items(), 
                                   key=lambda x: sum(x[1].values()), 
                                   reverse=True)[:3]
                context.append("\nTop 3 villes actives:")
                for city, stats in top_cities:
                    context.append("  • {}: {} commandes".format(city, sum(stats.values())))
        
        # Top livreurs
        if self.consumer_b:
            courier_stats = self.consumer_b.get_courier_stats()
            if courier_stats:
                top_couriers = sorted(courier_stats.items(),
                                     key=lambda x: x[1]['deliveries'],
                                     reverse=True)[:3]
                context.append("\nTop 3 livreurs:")
                for cid, stats in top_couriers:
                    context.append("  • {}: {} livraisons".format(cid, stats['deliveries']))
        
        return "\n".join(context)
    
    def process_question(self, question: str) -> str:
        """
        Traite une question et retourne la réponse.
        """
        question_lower = question.lower()
        
        # Pattern pour "commande ORD-xxx"
        order_match = re.search(r'ord[-\s]?\w+', question_lower, re.IGNORECASE)
        if order_match:
            order_id = order_match.group(0).upper()
            if not order_id.startswith('ORD-'):
                order_id = 'ORD-' + order_id.replace('ord', '').strip('-')
            return self.get_order_status_text(order_id)
        
        # Pattern pour "livreur CRR-xxx"
        courier_match = re.search(r'crr[-\s]?\w+', question_lower, re.IGNORECASE)
        if courier_match:
            courier_id = courier_match.group(0).upper()
            return self.get_courier_stats_text(courier_id)
        
        # Pattern pour "ville X"
        if 'ville' in question_lower:
            for city in ['Fes', 'Casablanca', 'Rabat', 'Marrakech', 'Tanger']:
                if city.lower() in question_lower:
                    return self.get_city_stats_text(city)
            return self.get_city_stats_text()
        
        # Pattern pour statistiques globales
        if any(word in question_lower for word in ['statistique', 'global', 'performance', 'taux']):
            return self.get_global_stats_text()
        
        # Pattern pour livreurs
        if 'livreur' in question_lower:
            if 'top' in question_lower or 'meilleur' in question_lower:
                return self.get_courier_stats_text()
            return self.get_courier_stats_text()
        
        # Si aucun pattern ne correspond, retourner None pour que l'IA réponde
        return None