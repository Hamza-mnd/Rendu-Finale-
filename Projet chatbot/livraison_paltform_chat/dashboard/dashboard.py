"""Tableau de bord texte interactif."""

import os
import json
import time
import threading
from datetime import datetime
from typing import Dict, Any


class Dashboard:
    """Tableau de bord texte affichant les indicateurs de performance."""
    
    def __init__(self, consumer_a, consumer_b, broker, update_interval: float = 10.0):
        self.consumer_a = consumer_a
        self.consumer_b = consumer_b
        self.broker = broker
        self.update_interval = update_interval
        self.running = False
        self.thread = None
        
    def _clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _format_number(self, n: int) -> str:
        return f"{n:,}".replace(",", " ")
    
    def _format_percent(self, value: float) -> str:
        return f"{value:.1f}%"
    
    def _get_bar(self, percentage: float, width: int = 20) -> str:
        filled = int(width * percentage / 100)
        empty = width - filled
        return "█" * filled + "░" * empty
    
    def _render(self):
        self._clear_screen()
        
        print("=" * 80)
        print("📦 PLATEFORME DE LIVRAISON - TABLEAU DE BORD")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        print("\n📊 INDICATEURS GLOBAUX")
        print("-" * 40)
        
        if self.consumer_a:
            stats_a = self.consumer_a.get_stats()
            print(f"  Commandes créées :     {self._format_number(stats_a['total_created'])}")
            print(f"  Livraisons réussies :  {self._format_number(stats_a['total_delivered'])}")
            print(f"  Livraisons échouées :  {self._format_number(stats_a['total_failed'])}")
            print(f"  Commandes annulées :   {self._format_number(stats_a['total_cancelled'])}")
            print(f"  Taux de succès :       {self._format_percent(stats_a['success_rate'])}")
            bar = self._get_bar(stats_a['success_rate'])
            print(f"                         [{bar}]")
        
        print("\n🏙️ ACTIVITÉ PAR VILLE")
        print("-" * 40)
        
        if self.consumer_a:
            city_activity = self.consumer_a.stats_by_city
            if city_activity:
                for city, stats in sorted(city_activity.items(), key=lambda x: sum(x[1].values()), reverse=True):
                    total = sum(stats.values())
                    print(f"  {city:12} : {self._format_number(total)} commandes")
        
        print("\n👤 STATS LIVREURS")
        print("-" * 40)
        
        if self.consumer_b:
            courier_stats = self.consumer_b.get_courier_stats()
            print(f"  Total livraisons : {self._format_number(self.consumer_b.total_deliveries)}")
            print(f"  Total échecs :     {self._format_number(self.consumer_b.total_failures)}")
        
        print("\n" + "=" * 80)
        print(f"🔄 Mise à jour toutes les {self.update_interval}s | Ctrl+C pour quitter")
    
    def _update_loop(self):
        while self.running:
            self._render()
            time.sleep(self.update_interval)
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._update_loop)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
    
    def export_report(self, filename: str = "rapport_final.json"):
        report = {
            'generated_at': datetime.now().isoformat(),
            'indicators': {}
        }
        
        if self.consumer_a:
            report['indicators']['consumer_a'] = self.consumer_a.get_stats()
        
        if self.consumer_b:
            report['indicators']['consumer_b'] = {
                'total_deliveries': self.consumer_b.total_deliveries,
                'total_failures': self.consumer_b.total_failures,
                'couriers': self.consumer_b.get_courier_stats()
            }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 Rapport exporté vers {filename}")