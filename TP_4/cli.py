"""cli.py — Interface CLI + démo intégrée du service RPC (Séance 4).

Usage démo (sans serveur réel) :
    python cli.py --demo

Usage avec serveur (démarrer server.py d'abord) :
    python cli.py ping
    python cli.py ingest
    python cli.py stats --date 2026-03-09
    python cli.py top --n 3
"""
import argparse
import json
import threading
import time

from src.router import MethodRouter
from src.rpc_protocol import build_request, build_response, build_error_response, validate_rpc_request
from src.services import health_ping, ingest_batch, stats_daily_summary, stats_top_sensors, store
from src.observability import StructuredLogger, MetricsCollector

# ============================================================
# DONNÉES DE TEST (10 lectures, 6 valides, 4 erronées)
# ============================================================
TEST_BATCH = [
    {"sensor_id": "S01", "ts": "2026-03-09T10:00:00", "value": 23.5},
    {"sensor_id": "S02", "ts": "2026-03-09T10:00:00", "value": 18.2},
    {"sensor_id": "S03", "ts": "2026-03-09T10:05:00", "value": -5.1},
    {"sensor_id": "",    "ts": "2026-03-09T10:10:00", "value": 22.0},   # ❌ sensor_id vide
    {"sensor_id": "S01", "ts": "2026-03-09T10:15:00", "value": 25.3},
    {"sensor_id": "S04", "ts": "2026-03-09T10:20:00", "value": "abc"}, # ❌ value non numérique
    {"sensor_id": "S02", "ts": "2026-03-09T10:25:00", "value": 19.8},
    {"sensor_id": "S05", "ts": "",                     "value": 30.0},  # ❌ ts manquant
    {"sensor_id": "S03", "ts": "2026-03-09T10:30:00", "value": 9999.9},# ❌ valeur aberrante
    {"sensor_id": "S01", "ts": "2026-03-09T10:35:00", "value": 24.1},
]


def run_demo():
    """Démo intégrée sans réseau — pipeline RPC complet."""
    print("=" * 60)
    print("  DÉMO TP4 — Mini RPC Data Service (sans réseau)")
    print("=" * 60)

    router  = MethodRouter()
    metrics = MetricsCollector()
    logger  = StructuredLogger("demo")

    router.register("health.ping",         health_ping)
    router.register("ingest.batch",        ingest_batch)
    router.register("stats.daily_summary", stats_daily_summary)
    router.register("stats.top_sensors",   stats_top_sensors)

    print(f"\nMéthodes disponibles : {router.list_methods()}")

    def call(method, params=None):
        """Simule un appel RPC complet (build → validate → dispatch → réponse)."""
        req_dict = build_request(method, params or {})
        raw      = json.dumps(req_dict).encode("utf-8")
        parsed, err = validate_rpc_request(raw)
        if err:
            return err
        start = time.monotonic()
        try:
            result   = router.dispatch(parsed["method"], parsed.get("params", {}))
            resp     = build_response(parsed["id"], result)
            success  = True
        except KeyError:
            resp    = build_error_response(parsed["id"], -32601, "Method not found")
            success = False
        except (ValueError, TypeError) as e:
            resp    = build_error_response(parsed["id"], -32602, "Invalid params", str(e))
            success = False
        except Exception as e:
            resp    = build_error_response(parsed["id"], -32603, "Internal error", str(e))
            success = False
        finally:
            dur = (time.monotonic() - start) * 1000
            metrics.record_call(method, dur, success)
            logger.info(parsed["id"], method, "call completed",
                        duration_ms=round(dur, 3), success=success)
        return resp

    # ---- 1. health.ping ----
    print("\n[1] health.ping")
    r = call("health.ping")
    print(f"    → {r['result']}")

    # ---- 2. ingest.batch ----
    print("\n[2] ingest.batch (10 lectures)")
    r = call("ingest.batch", {"readings": TEST_BATCH})
    res = r["result"]
    print(f"    → accepted={res['accepted']}, rejected={res['rejected']}")
    for e in res["errors"]:
        print(f"       ❌ index={e['index']} | {e.get('errors', e.get('error', ''))}")

    # ---- 3. stats.daily_summary ----
    print("\n[3] stats.daily_summary (2026-03-09)")
    r = call("stats.daily_summary", {"date": "2026-03-09"})
    print(f"    → {r['result']}")

    # ---- 4. stats.top_sensors ----
    print("\n[4] stats.top_sensors (n=3)")
    r = call("stats.top_sensors", {"n": 3})
    for s in r["result"]["sensors"]:
        print(f"       {s['sensor_id']} : avg={s['avg']}")

    # ---- 5. Méthode inconnue ----
    print("\n[5] Méthode inconnue (unknown.method)")
    r = call("unknown.method")
    print(f"    → erreur code={r['error']['code']} : {r['error']['message']}")

    # ---- 6. Paramètre invalide ----
    print("\n[6] Paramètre invalide (date manquante)")
    r = call("stats.daily_summary", {})
    print(f"    → erreur code={r['error']['code']} : {r['error']['message']}")

    # ---- Assertions ----
    print("\n--- Vérifications ---")

    ingest_result = call("ingest.batch", {"readings": TEST_BATCH})["result"]
    # On a déjà ingéré → store non vide, on reteste la logique
    assert ingest_result["accepted"] == 6, \
        f"Attendu 6 acceptés, obtenu {ingest_result['accepted']}"
    print("[OK] 6 lectures acceptées, 4 rejetées")

    summary = call("stats.daily_summary", {"date": "2026-03-09"})["result"]
    assert summary["count"] > 0
    assert summary["min"] == -5.1
    assert summary["max"] == 25.3
    print(f"[OK] daily_summary : count={summary['count']}, min={summary['min']}, max={summary['max']}")

    top = call("stats.top_sensors", {"n": 2})["result"]["sensors"]
    assert len(top) == 2
    print(f"[OK] top_sensors (n=2) : {[s['sensor_id'] for s in top]}")

    ping = call("health.ping")["result"]
    assert ping["status"] == "ok"
    print("[OK] health.ping retourne status=ok")

    err_resp = call("unknown.method")
    assert err_resp["error"]["code"] == -32601
    print("[OK] Méthode inconnue → code -32601")

    validate_result = validate_rpc_request(b"not json")
    assert validate_result[1]["error"]["code"] == -32700
    print("[OK] JSON invalide → code -32700")

    validate_result2 = validate_rpc_request(b'{"id":"x","method":"health.ping"}')
    assert validate_result2[0] is not None
    print("[OK] Requête valide → parsée correctement")

    report = metrics.get_report()
    assert "health.ping" in report
    assert "ingest.batch" in report
    print("[OK] Métriques collectées pour toutes les méthodes")

    # Export CSV
    exported = store.export_csv("outputs/ingested_data.csv")
    assert exported > 0
    print(f"[OK] CSV exporté : {exported} lignes → outputs/ingested_data.csv")

    # Export rapport métriques
    with open("outputs/run_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("[OK] Rapport métriques exporté → outputs/run_report.json")

    print("\n✅ Toutes les vérifications passent !")
    print("\n💡 Pour le mode réseau réel :")
    print("   Terminal 1 → python server.py")
    print("   Terminal 2 → python cli.py ping")


# ============================================================
# CLI ARGPARSE
# ============================================================
def build_cli():
    parser = argparse.ArgumentParser(description="Client CLI — RPC Data Service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--demo", action="store_true",
                        help="Lancer la démo intégrée sans serveur")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("ping", help="health.ping")

    sub.add_parser("ingest", help="ingest.batch avec le jeu de données de test")

    p_stats = sub.add_parser("stats", help="stats.daily_summary")
    p_stats.add_argument("--date", default="2026-03-09")

    p_top = sub.add_parser("top", help="stats.top_sensors")
    p_top.add_argument("--n", type=int, default=5)

    return parser


if __name__ == "__main__":
    parser = build_cli()
    args   = parser.parse_args()

    if args.demo or args.command is None:
        run_demo()
    else:
        from src.client import RpcClient
        url    = f"http://{args.host}:{args.port}"
        client = RpcClient(url)

        try:
            if args.command == "ping":
                r = client.call("health.ping")

            elif args.command == "ingest":
                r = client.call("ingest.batch", {"readings": TEST_BATCH})

            elif args.command == "stats":
                r = client.call("stats.daily_summary", {"date": args.date})

            elif args.command == "top":
                r = client.call("stats.top_sensors", {"n": args.n})

            print(json.dumps(r, indent=2, ensure_ascii=False))

        except ConnectionError as e:
            print(f"❌ Connexion échouée : {e}")
