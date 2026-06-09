"""client.py — Client TCP pour l'envoi de mesures IoT (Séance 3).

Usage :
    python client.py [--host 127.0.0.1] [--port 9000] [--file data/sample_readings.json]

Le client :
  1. Charge les lectures depuis un fichier JSON
  2. Construit un IngestRequest et l'enveloppe dans un message protocolaire
  3. Envoie la requête au serveur via TCP
  4. Affiche un résumé clair de la réponse
"""
import socket
import json
import logging
import argparse

from src.models import IngestRequest, SensorReading, IngestResponse
from src.protocol import encode_message, recv_line, decode_message, build_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingestion.client")


def load_readings(filepath: str) -> list[dict]:
    """Charge les lectures depuis un fichier JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def send_ingest_request(host: str, port: int, request_msg: dict,
                        timeout: float = 10.0) -> dict | None:
    """Envoie un message protocolaire et retourne la réponse décodée.

    Args:
        host:        Adresse du serveur.
        port:        Port du serveur.
        request_msg: Message conforme au protocole v1.
        timeout:     Délai max en secondes.

    Returns:
        Dictionnaire de réponse ou None en cas d'erreur.
    """
    request_id = request_msg.get("request_id", "?")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            logger.info("[%s] Connexion à %s:%d …", request_id, host, port)
            sock.connect((host, port))

            payload_bytes = encode_message(request_msg)
            sock.sendall(payload_bytes)
            logger.info("[%s] Requête envoyée (%d octets)",
                        request_id, len(payload_bytes))

            # Lire la réponse NDJSON
            buffer = bytearray()
            line = recv_line(sock, buffer)
            if line is None:
                logger.error("[%s] Pas de réponse du serveur", request_id)
                return None

            response = decode_message(line)
            logger.info("[%s] Réponse reçue : type=%s",
                        request_id, response.get("type"))
            return response

    except socket.timeout:
        logger.error("[%s] ⏱ Timeout (serveur trop lent ou inaccessible)", request_id)
    except ConnectionRefusedError:
        logger.error("[%s] 🚫 Connexion refusée — le serveur est-il démarré ?", request_id)
    except ConnectionResetError:
        logger.error("[%s] 💥 Connexion réinitialisée par le serveur", request_id)
    except OSError as e:
        logger.error("[%s] Erreur réseau : %s", request_id, e)
    return None


def print_summary(response: dict):
    """Affiche un résumé lisible de la réponse du serveur."""
    payload = response.get("payload", {})
    print("\n" + "=" * 55)
    print("  RÉSUMÉ DE LA RÉPONSE SERVEUR")
    print("=" * 55)
    print(f"  request_id      : {payload.get('request_id', '?')}")
    print(f"  ✅ Acceptées    : {payload.get('accepted_count', 0)}")
    print(f"  ❌ Rejetées     : {payload.get('rejected_count', 0)}")
    print(f"  ⏱  Traitement   : {payload.get('processing_time_ms', 0):.2f} ms")

    errors = payload.get("errors", [])
    if errors:
        print(f"\n  Erreurs détectées ({len(errors)}) :")
        for e in errors:
            print(f"    • [{e['sensor_id']}] {e['field']} — {e['message']}")
    else:
        print("\n  Aucune erreur — toutes les lectures acceptées ✅")
    print("=" * 55)


def run_client(host: str, port: int, filepath: str):
    """Point d'entrée principal du client."""
    # 1. Charger les données
    raw_readings = load_readings(filepath)
    logger.info("Chargement de %d lecture(s) depuis '%s'",
                len(raw_readings), filepath)

    # 2. Construire l'IngestRequest
    readings = [SensorReading.from_dict(r) for r in raw_readings]
    ingest_req = IngestRequest(source="station_agricole_01", readings=readings)

    # 3. Envelopper dans le protocole v1
    msg = build_message("ingest_request", ingest_req.to_dict())

    # 4. Envoyer et afficher la réponse
    response = send_ingest_request(host, port, msg)
    if response:
        print_summary(response)
    else:
        print("\n❌ Aucune réponse reçue du serveur.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client TCP d'ingestion IoT")
    parser.add_argument("--host", default="127.0.0.1", help="Adresse du serveur")
    parser.add_argument("--port", type=int, default=9000, help="Port du serveur")
    parser.add_argument("--file", default="data/sample_readings.json",
                        help="Fichier JSON des lectures à envoyer")
    args = parser.parse_args()
    run_client(args.host, args.port, args.file)
