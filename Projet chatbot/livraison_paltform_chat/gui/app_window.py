"""app_window.py — Interface graphique corrigée (v3)."""
import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import os
import sys
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

try:
    from ai_assistant import ChatBot, load_api_key, QueryEngine
    AI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ IA non disponible: {e}")
    AI_AVAILABLE = False

# Couleurs
BG       = "#0d1117"
BG_PANEL = "#161b22"
BG_HDR   = "#1f2937"
BG_USER  = "#1d4ed8"
BG_BOT   = "#166534"
BG_ENTRY = "#21262d"
FG       = "#e6edf3"
FG_MUT   = "#8b949e"
ACCENT   = "#58a6ff"
GREEN    = "#3fb950"
RED      = "#f85149"
YELLOW   = "#d29922"


class DeliveryPlatformApp(tk.Tk):

    def __init__(self, platform_instance):
        super().__init__()
        self.platform = platform_instance
        self.bot = None
        self.query_engine = None

        self.title("📦 Plateforme de Livraison — Assistant IA")
        self.geometry("1280x720")
        self.minsize(900, 550)
        self.configure(bg=BG)

        self._init_ai()
        self._build_ui()
        self._start_auto_refresh()
        self.after(600, self._welcome)

    # ── IA ────────────────────────────────────────────────

    def _init_ai(self):
        if not AI_AVAILABLE:
            return
        try:
            key = load_api_key()
            if key:
                self.bot = ChatBot(api_key=key)
                self.query_engine = QueryEngine(
                    self.platform.order_service,
                    self.platform.consumer_a,
                    self.platform.consumer_b,
                    self.platform.broker,
                )
                print(f"✓ Groq initialisé ({key[:12]}...)")
            else:
                print("❌ Clé API non trouvée")
        except Exception as e:
            print(f"❌ init AI: {e}")

    # ── UI ────────────────────────────────────────────────

    def _build_ui(self):
        # En-tête
        hdr = tk.Frame(self, bg=BG_HDR, pady=8)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="📦 Plateforme de Livraison — Assistant IA",
                 bg=BG_HDR, fg=ACCENT, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT, padx=16)
        ai_txt = "Groq IA ✓" if self.bot else "Mode local"
        ai_col = GREEN if self.bot else YELLOW
        tk.Label(hdr, text=ai_txt, bg=BG_HDR, fg=ai_col,
                 font=("Segoe UI", 10)).pack(side=tk.RIGHT, padx=16)

        # Corps : gauche dashboard, droite chat
        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(body, bg=BG_PANEL, width=460)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=(8, 4), pady=8)
        left.pack_propagate(False)

        right = tk.Frame(body, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=8)

        self._build_dashboard(left)
        self._build_chat(right)

    def _build_dashboard(self, p):
        top = tk.Frame(p, bg=BG_PANEL)
        top.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(top, text="📊 TABLEAU DE BORD", bg=BG_PANEL,
                 fg=ACCENT, font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        tk.Button(top, text="↺ Rafraîchir", command=self._refresh,
                  bg=BG_ENTRY, fg=FG, font=("Segoe UI", 9),
                  relief=tk.FLAT, padx=8, cursor="hand2").pack(side=tk.RIGHT)

        self.dash = scrolledtext.ScrolledText(
            p, bg=BG_PANEL, fg=FG, font=("Consolas", 9),
            relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED)
        self.dash.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        btns = tk.Frame(p, bg=BG_PANEL)
        btns.pack(fill=tk.X, padx=8, pady=(0, 8))
        for txt, cmd, col in [
            ("📦 Envoyer commandes test", self._send_test,  "#e94560"),
            ("📄 Exporter rapport",       self._export,     BG_ENTRY),
        ]:
            tk.Button(btns, text=txt, command=cmd, bg=col, fg=FG,
                      font=("Segoe UI", 9), relief=tk.FLAT,
                      padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=4)

    def _build_chat(self, p):
        top = tk.Frame(p, bg=BG)
        top.pack(fill=tk.X, pady=(0, 4))
        tk.Label(top, text="🤖 ASSISTANT IA", bg=BG,
                 fg=ACCENT, font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        tk.Button(top, text="🗑 Effacer", command=self._clear,
                  bg=BG_ENTRY, fg=FG_MUT, font=("Segoe UI", 9),
                  relief=tk.FLAT, padx=8, cursor="hand2").pack(side=tk.RIGHT)

        # Canvas scrollable pour les messages
        cf = tk.Frame(p, bg=BG)
        cf.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(cf, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(cf, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.mf = tk.Frame(self.canvas, bg=BG)
        self._cw = self.canvas.create_window((0, 0), window=self.mf, anchor="nw")
        self.mf.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self._cw, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))

        # Suggestions
        sf = tk.Frame(p, bg=BG)
        sf.pack(fill=tk.X, pady=(6, 3))
        for s in ["📊 Statistiques globales", "👤 Livreurs",
                  "🏙️ Activité par ville", "📦 Commandes en cours"]:
            tk.Button(sf, text=s, command=lambda x=s: self._suggest(x),
                      bg=BG_HDR, fg=FG_MUT, font=("Segoe UI", 9),
                      relief=tk.FLAT, padx=8, pady=3,
                      cursor="hand2").pack(side=tk.LEFT, padx=3)

        # Saisie
        ef = tk.Frame(p, bg=BG_ENTRY, pady=4)
        ef.pack(fill=tk.X, pady=(3, 0))
        self.entry = tk.Entry(ef, bg=BG_ENTRY, fg=FG,
                              font=("Segoe UI", 11),
                              insertbackground=FG, relief=tk.FLAT, bd=0)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 4), pady=4)
        self.entry.bind("<Return>", lambda e: self._send())
        self.send_btn = tk.Button(ef, text="Envoyer ➤", command=self._send,
                                  bg=ACCENT, fg=BG, font=("Segoe UI", 10, "bold"),
                                  relief=tk.FLAT, padx=12, pady=5, cursor="hand2")
        self.send_btn.pack(side=tk.RIGHT, padx=8)

    # ── DASHBOARD ─────────────────────────────────────────

    def _refresh(self):
        try:
            stats  = self.platform.consumer_a.get_stats()
            cb     = self.platform.consumer_b
            broker = self.platform.broker

            self.dash.config(state=tk.NORMAL)
            self.dash.delete(1.0, tk.END)

            def w(t=""): self.dash.insert(tk.END, t + "\n")

            w(f"  Mise à jour : {datetime.now().strftime('%H:%M:%S')}")
            w("═" * 44)
            w()
            w("📈 INDICATEURS GLOBAUX")
            w("─" * 28)
            w(f"  Commandes créées    : {stats.get('total_created', 0):>5}")
            w(f"  Livraisons réussies : {stats.get('total_delivered', 0):>5}")
            w(f"  Livraisons échouées : {stats.get('total_failed', 0):>5}")
            w(f"  Commandes annulées  : {stats.get('total_cancelled', 0):>5}")
            sr = stats.get('success_rate', 0)
            bar = "█" * int(sr / 5) + "░" * (20 - int(sr / 5))
            w(f"  Taux de succès      : {sr:>5.1f}%")
            w(f"  [{bar}]")
            w(f"  Backlog             : {stats.get('backlog', 0):>5}")
            w()

            by_city = stats.get('by_city', {})
            w("🏙️ ACTIVITÉ PAR VILLE")
            w("─" * 28)
            if by_city:
                for city, cs in sorted(by_city.items(),
                                       key=lambda x: sum(x[1].values()),
                                       reverse=True):
                    total     = sum(cs.values())
                    delivered = cs.get('order_delivered', 0)
                    w(f"  {city:<12} : {total:>3} cmds  {delivered:>3} livrées")
            else:
                w("  Aucune donnée — cliquez 'Envoyer commandes test'")
            w()

            w("👤 STATS LIVREURS")
            w("─" * 28)
            if cb:
                courier_stats = cb.get_courier_stats()
                if courier_stats:
                    for cid, cs in sorted(courier_stats.items()):
                        w(f"  {cid:<8} : {cs.get('deliveries', 0):>3} liv."
                          f"  taux {cs.get('success_rate', 100):.0f}%")
                else:
                    w(f"  Livraisons totales : {cb.total_deliveries}")
                    w(f"  Échecs totaux      : {cb.total_failures}")

            w()
            w("📡 BROKER — PARTITIONS")
            w("─" * 28)
            for i in range(broker.num_partitions):
                sz = broker.get_partition_size(i)
                w(f"  Partition {i} : {sz:>4} messages")

            self.dash.config(state=tk.DISABLED)

        except Exception as e:
            print(f"Refresh error: {e}")
            import traceback; traceback.print_exc()

    def _send_test(self):
        self._bot_msg("📦 Envoi des commandes de test...")

        def do():
            try:
                self.platform.send_test_orders()
                self.after(0, lambda: self._bot_msg(
                    "✅ Commandes de test envoyées !\n"
                    "Cliquez sur '↺ Rafraîchir' pour voir les stats."
                ))
                self.after(1000, self._refresh)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                self.after(0, lambda: self._bot_msg(f"❌ Erreur: {e}\n{tb[:300]}"))

        threading.Thread(target=do, daemon=True).start()

    def _export(self):
        try:
            fname = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            if self.platform.dashboard:
                self.platform.dashboard.export_report(fname)
            self._bot_msg(f"📄 Rapport exporté → {fname}")
        except Exception as e:
            self._bot_msg(f"❌ Export: {e}")

    # ── CHAT ──────────────────────────────────────────────

    def _add_msg(self, sender, text, is_user):
        outer = tk.Frame(self.mf, bg=BG)
        outer.pack(fill=tk.X, padx=8, pady=4)
        anchor = tk.E if is_user else tk.W
        pad_l  = 80 if is_user else 4
        pad_r  = 4  if is_user else 80
        col    = BG_USER if is_user else BG_BOT

        tk.Label(outer, text=sender, bg=BG, fg=FG_MUT,
                 font=("Segoe UI", 8)).pack(anchor=anchor, padx=(pad_l, pad_r))
        tk.Label(outer, text=text, bg=col, fg=FG,
                 font=("Segoe UI", 10), wraplength=500,
                 justify=tk.LEFT, padx=14, pady=9,
                 anchor="w").pack(anchor=anchor, padx=(pad_l, pad_r))

        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _bot_msg(self, t):  self._add_msg("🤖 Assistant", t, False)
    def _user_msg(self, t): self._add_msg("👤 Vous", t, True)

    def _send(self):
        txt = self.entry.get().strip()
        if not txt:
            return
        self.entry.delete(0, tk.END)
        self._user_msg(txt)
        self.send_btn.config(state=tk.DISABLED, text="⏳")

        def process():
            reply = self._reply(txt)
            self.after(0, lambda: self._finish(reply))

        threading.Thread(target=process, daemon=True).start()

    def _reply(self, q: str) -> str:
        # 1. Query engine local
        if self.query_engine:
            try:
                r = self.query_engine.process_question(q)
                if r:
                    return r
            except Exception as e:
                print(f"QE error: {e}")
        # 2. Groq IA
        if self.bot:
            try:
                ctx = self.query_engine.get_all_context() if self.query_engine else ""
                return self.bot.send_message(q, context=ctx)
            except Exception as e:
                return f"❌ Groq API: {e}"
        # 3. Fallback local
        return self._fallback(q)

    def _fallback(self, q: str) -> str:
        ql = q.lower()
        try:
            stats = self.platform.consumer_a.get_stats()
            if any(w in ql for w in ["stat", "global", "total", "bilan", "résumé"]):
                return (
                    f"📊 Statistiques globales :\n"
                    f"• Commandes créées : {stats.get('total_created', 0)}\n"
                    f"• Livrées : {stats.get('total_delivered', 0)}\n"
                    f"• Échouées : {stats.get('total_failed', 0)}\n"
                    f"• Taux de succès : {stats.get('success_rate', 0):.1f}%\n"
                    f"• Backlog : {stats.get('backlog', 0)}"
                )
            if any(w in ql for w in ["ville", "city", "activité"]):
                bc = stats.get('by_city', {})
                if not bc:
                    return "Aucune activité. Envoyez des commandes test d'abord."
                r = "🏙️ Activité par ville :\n"
                for city, cs in sorted(bc.items(), key=lambda x: sum(x[1].values()), reverse=True):
                    r += f"• {city} : {sum(cs.values())} événements\n"
                return r
            if any(w in ql for w in ["livreur", "crr", "courier"]):
                cb = self.platform.consumer_b
                if cb:
                    cs = cb.get_courier_stats()
                    if cs:
                        r = "👤 Livreurs :\n"
                        for cid, d in sorted(cs.items()):
                            r += f"• {cid} : {d.get('deliveries', 0)} livraisons taux {d.get('success_rate', 100):.0f}%\n"
                        return r
                    return f"Total livraisons : {cb.total_deliveries}"
            if any(w in ql for w in ["commande", "ord"]):
                return f"📦 {stats.get('total_created', 0)} commandes créées, {stats.get('backlog', 0)} en attente."
        except Exception as e:
            return f"❌ Erreur : {e}"
        return "Posez-moi des questions sur les commandes, les livreurs ou les statistiques."

    def _finish(self, reply):
        self._bot_msg(reply)
        self.send_btn.config(state=tk.NORMAL, text="Envoyer ➤")
        self.entry.focus_set()

    def _suggest(self, s):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, s)
        self._send()

    def _clear(self):
        for w in self.mf.winfo_children():
            w.destroy()
        if self.bot:
            self.bot.clear_history()
        self._bot_msg("🔄 Chat effacé. Comment puis-je vous aider ?")

    def _welcome(self):
        ai = "Groq IA active ✓" if self.bot else "mode local"
        self._bot_msg(
            f"👋 Bonjour ! Plateforme de livraison prête ({ai}).\n\n"
            "Cliquez sur 📦 'Envoyer commandes test' pour générer des données,\n"
            "puis posez-moi des questions :\n"
            "• Statistiques globales\n"
            "• Performance du livreur CRR-01\n"
            "• Activité par ville\n"
            "• Statut commande ORD-xxxx"
        )

    def _start_auto_refresh(self):
        def loop():
            while True:
                time.sleep(5)
                try:
                    self.after(0, self._refresh)
                except Exception:
                    break
        threading.Thread(target=loop, daemon=True).start()
