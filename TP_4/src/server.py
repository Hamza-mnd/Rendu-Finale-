"""server.py — Serveur HTTP-RPC threaded (Séance 4).

Usage :
    python server.py [--host 127.0.0.1] [--port 8080]
"""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import time
import traceback
import os
import argparse

from src.router import MethodRouter
from src.rpc_protocol import validate_rpc_request, build_response, build_error_response
from src.services import health_ping, ingest_batch, stats_daily_summary, stats_top_sensors
from src.observability import StructuredLogger, MetricsCollector

os.makedirs("logs", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

logger  = StructuredLogger("rpc-server", log_file="logs/server.log")
metrics = MetricsCollector()


class RPCHandler(BaseHTTPRequestHandler):
    """Handler HTTP qui traite toutes les requêtes RPC sur POST /rpc."""

    def do_POST(self):
        start    = time.monotonic()
        rpc_id   = ""
        method   = ""
        success  = True

        try:
            # 1. Lire le body
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(build_error_response("", -32700, "Empty body"))
                success = False
                return

            raw_body = self.rfile.read(content_length)

            # 2. Valider la structure RPC
            parsed, error_resp = validate_rpc_request(raw_body)
            if error_resp:
                self._send_json(error_resp)
                success = False
                return

            rpc_id = parsed.get("id", "")
            method = parsed.get("method", "")
            logger.info(rpc_id, method, "Request received",
                        params_keys=list(parsed.get("params", {}).keys()))

            # 3. Router vers la méthode
            try:
                result   = self.server.router.dispatch(method, parsed.get("params", {}))
                response = build_response(rpc_id, result)
                self._send_json(response)
                logger.info(rpc_id, method, "Request succeeded")

            except KeyError:
                response = build_error_response(
                    rpc_id, -32601, "Method not found",
                    f"Méthode inconnue : {method}"
                )
                self._send_json(response)
                success = False
                logger.warn(rpc_id, method, "Method not found")

            except (ValueError, TypeError) as e:
                response = build_error_response(
                    rpc_id, -32602, "Invalid params", str(e)
                )
                self._send_json(response)
                success = False
                logger.warn(rpc_id, method, f"Invalid params: {e}")

            except OverflowError as e:
                response = build_error_response(
                    rpc_id, 1002, "Payload too large", str(e)
                )
                self._send_json(response)
                success = False
                logger.warn(rpc_id, method, f"Payload too large: {e}")

            except Exception as e:
                tb = traceback.format_exc()
                response = build_error_response(
                    rpc_id, -32603, "Internal error",
                    "Une erreur interne s'est produite"
                )
                self._send_json(response)
                success = False
                logger.error(rpc_id, method, f"Internal error: {e}",
                             traceback=tb)

        except Exception as e:
            # Dernier filet de sécurité
            try:
                self._send_json(
                    build_error_response("", -32603, "Internal error", "Server failure")
                )
            except Exception:
                pass
            success = False

        finally:
            duration_ms = (time.monotonic() - start) * 1000
            metrics.record_call(method or "unknown", duration_ms, success)
            logger.info(rpc_id, method, "Request completed",
                        duration_ms=round(duration_ms, 2), success=success)

    def _send_json(self, data: dict):
        """Envoie une réponse HTTP 200 avec body JSON."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Désactiver les logs HTTP par défaut (remplacés par StructuredLogger)


def create_server(host: str = "127.0.0.1", port: int = 8080):
    """Crée et configure le serveur RPC."""
    server = ThreadingHTTPServer((host, port), RPCHandler)
    server.router = MethodRouter()

    # Enregistrement des 4 méthodes
    server.router.register("health.ping",          health_ping)
    server.router.register("ingest.batch",         ingest_batch)
    server.router.register("stats.daily_summary",  stats_daily_summary)
    server.router.register("stats.top_sensors",    stats_top_sensors)

    methods = server.router.list_methods()
    logger.info("", "server", f"Serveur démarré sur {host}:{port}",
                methods=methods)
    print(f"🚀 Serveur RPC démarré sur http://{host}:{port}")
    print(f"   Méthodes disponibles : {methods}")
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serveur HTTP-RPC IoT")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    srv = create_server(args.host, args.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
        report = metrics.get_report()
        with open("outputs/run_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("📊 Rapport exporté dans outputs/run_report.json")
        srv.server_close()
