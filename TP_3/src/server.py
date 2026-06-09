"""server.py — Serveur TCP d'ingestion IoT (Séance 3).

Usage :
    python server.py [--host 127.0.0.1] [--port 9000]

Le serveur :
  1. Écoute les connexions TCP entrantes
  2. Lit un message NDJSON par connexion
  3. Valide les lectures IoT
  4. Renvoie une IngestResponse JSON au client
  5. Logue tous les événements avec request_id
"""
import socket
import logging
import argparse
import time

from src.models import IngestRequest, IngestResponse
from src.validators import validate_readings
from src.protocol import recv_line, decode_message, encode_message, build_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingestion.server")


def handle_client(conn: socket.socket, addr: tuple):
    """Traite une connexion client unique (une requête → une réponse)."""
    buffer = bytearray()
    request_id = "unknown"
    start_time = time.time()

    try:
        conn.settimeout(30.0)

        # 1. Lire une ligne NDJSON complète
        line = recv_line(conn, buffer)
        if line is None:
            logger.warning("Connexion fermée immédiatement par %s", addr)
            return

        # 2. Décoder le message protocolaire
        msg = decode_message(line)
        request_id = msg.get("request_id", "unknown")
        msg_type   = msg.get("type", "")
        logger.info("[%s] Message reçu : type=%s depuis %s:%d",
                    request_id, msg_type, addr[0], addr[1])

        # 3. Gérer les types non supportés
        if msg_type == "ping":
            pong = build_message("pong", {"status": "ok"}, request_id=request_id)
            conn.sendall(encode_message(pong))
            logger.info("[%s] Ping → Pong", request_id)
            return

        if msg_type != "ingest_request":
            err = build_message("error",
                                {"message": f"Type non supporté : {msg_type}"},
                                request_id=request_id)
            conn.sendall(encode_message(err))
            logger.warning("[%s] Type inconnu : %s", request_id, msg_type)
            return

        # 4. Reconstruire la requête métier
        payload = msg.get("payload", {})
        ingest_req = IngestRequest.from_dict(payload)
        logger.info("[%s] %d lecture(s) à valider (source=%s)",
                    request_id, len(ingest_req.readings), ingest_req.source)

        # 5. Valider les lectures
        accepted, errors = validate_readings(ingest_req.readings)
        elapsed_ms = (time.time() - start_time) * 1000

        for e in errors:
            logger.warning("[%s]  ❌ sensor=%s | %s : %s",
                           request_id, e.sensor_id, e.field, e.message)

        # 6. Construire et envoyer la réponse
        response = IngestResponse(
            request_id=        request_id,
            accepted_count=    len(accepted),
            rejected_count=    len(errors),
            errors=            errors,
            processing_time_ms=round(elapsed_ms, 2),
        )
        resp_msg = build_message("ingest_response",
                                 response.to_dict(),
                                 request_id=request_id)
        conn.sendall(encode_message(resp_msg))

        logger.info("[%s] Réponse envoyée : accepted=%d, rejected=%d, %.2fms",
                    request_id, response.accepted_count,
                    response.rejected_count, elapsed_ms)

    except socket.timeout:
        logger.error("[%s] Timeout client %s", request_id, addr)
    except (ValueError, KeyError) as e:
        logger.error("[%s] Erreur de parsing : %s", request_id, e)
        try:
            err_msg = build_message("error", {"message": str(e)},
                                    request_id=request_id)
            conn.sendall(encode_message(err_msg))
        except OSError:
            pass
    except OSError as e:
        logger.error("[%s] Erreur réseau : %s", request_id, e)
    finally:
        conn.close()
        logger.debug("[%s] Connexion fermée", request_id)


def run_server(host: str = "127.0.0.1", port: int = 9000):
    """Lance la boucle principale du serveur TCP."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(5)
        logger.info("🚀 Serveur en écoute sur %s:%d (Ctrl+C pour arrêter)", host, port)

        while True:
            try:
                conn, addr = srv.accept()
                logger.info("Connexion acceptée depuis %s:%d", addr[0], addr[1])
                handle_client(conn, addr)
            except KeyboardInterrupt:
                logger.info("Arrêt du serveur (Ctrl+C)")
                break
            except OSError as e:
                logger.error("Erreur accept : %s", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serveur TCP d'ingestion IoT")
    parser.add_argument("--host", default="127.0.0.1", help="Adresse d'écoute")
    parser.add_argument("--port", type=int, default=9000, help="Port d'écoute")
    args = parser.parse_args()
    run_server(args.host, args.port)
