# dashboard/dashboard.py
import json, time, threading
from datetime import datetime
from pathlib import Path


class Dashboard:
    """
    Tableau de bord texte affiché dans la console, mis à jour toutes les 10 secondes.
    Lit les agrégats directement depuis les consumers (pas les fichiers disque).
    """

    def __init__(self, consumer_a, consumer_b, broker, offsets_a, offsets_b,
                 refresh_s: int = 10, stop_event: threading.Event = None):
        self.consumer_a = consumer_a
        self.consumer_b = consumer_b
        self.broker = broker
        self.offsets_a = offsets_a
        self.offsets_b = offsets_b
        self.refresh_s = refresh_s
        self.stop_event = stop_event or threading.Event()

    def run(self) -> None:
        while not self.stop_event.is_set():
            self._render()
            time.sleep(self.refresh_s)

    def _render(self) -> None:
        snap_a = self.consumer_a.snapshot()
        snap_b = self.consumer_b.snapshot()
        by_status = snap_a.get("by_status", {})
        by_city   = snap_a.get("by_city", {})
        by_courier = snap_b.get("by_courier", {})

        created   = by_status.get("created", 0)
        delivered = by_status.get("delivered", 0)
        failed    = by_status.get("failed", 0)
        cancelled = by_status.get("cancelled", 0)
        taux = round(delivered / created * 100, 1) if created > 0 else 0.0
        backlog = max(0, created - delivered - cancelled)

        lag_a = self.broker.lag(self.offsets_a.all(), "group-a")
        lag_b = self.broker.lag(self.offsets_b.all(), "group-b")

        sep = "─" * 52
        print(f"\n╔{sep}╗")
        print(f"║  TABLEAU DE BORD — {datetime.utcnow().strftime('%H:%M:%S')} UTC{'':>14}║")
        print(f"╠{sep}╣")
        print(f"║  Commandes créées      : {created:<26}║")
        print(f"║  Livrées avec succès   : {delivered:<26}║")
        print(f"║  Livraisons échouées   : {failed:<26}║")
        print(f"║  Annulées              : {cancelled:<26}║")
        print(f"║  Taux de succès        : {taux:<25.1f}%║")
        print(f"║  Backlog               : {backlog:<26}║")
        print(f"╠{sep}╣")
        print(f"║  ACTIVITÉ PAR VILLE{'':<33}║")
        for city, n in sorted(by_city.items()):
            print(f"║    {city:<20}: {n:<24}║")
        print(f"╠{sep}╣")
        print(f"║  ACTIVITÉ PAR LIVREUR{'':<31}║")
        for cid, stats in sorted(by_courier.items()):
            s = f"total={stats['total']} livré={stats['delivered']} échec={stats['failed']}"
            print(f"║    {cid:<10}: {s:<36}║")
        print(f"╠{sep}╣")
        print(f"║  LAG Consumer A : {str(lag_a):<33}║")
        print(f"║  LAG Consumer B : {str(lag_b):<33}║")
        print(f"╚{sep}╝")

    def export_report(self, path: str = "rapport_final.json") -> None:
        snap_a = self.consumer_a.snapshot()
        snap_b = self.consumer_b.snapshot()
        report = {
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "consumer_a": snap_a,
            "consumer_b": snap_b,
            "broker_summary": self.broker.summary(),
            "lag_a": self.broker.lag(self.offsets_a.all(), "group-a"),
            "lag_b": self.broker.lag(self.offsets_b.all(), "group-b"),
        }
        Path(path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nRapport exporté → {path}")
