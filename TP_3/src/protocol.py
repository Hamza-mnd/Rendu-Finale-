"""protocol.py — Encodage, décodage et framing NDJSON (Séance 3).

Protocole v1 :
  - Format  : JSON compact sur une seule ligne, terminé par \\n (NDJSON)
  - Champs  : version, type, request_id (UUID), sent_at (ISO 8601), payload
  - Types   : ingest_request | ingest_response | ping | error
"""
import json
import socket
import uuid
from datetime import datetime

PROTOCOL_VERSION = "v1"
MAX_MESSAGE_SIZE = 1_048_576  # 1 Mo


def build_message(msg_type: str, payload: dict,
                  request_id: str | None = None) -> dict:
    """Construit un message conforme au protocole v1.

    Args:
        msg_type:   Type du message (ex. 'ingest_request').
        payload:    Données métier à transporter.
        request_id: UUID de corrélation (généré si absent).

    Returns:
        Dictionnaire prêt à être encodé.
    """
    return {
        "version":    PROTOCOL_VERSION,
        "type":       msg_type,
        "request_id": request_id or str(uuid.uuid4()),
        "sent_at":    datetime.now().isoformat(),
        "payload":    payload,
    }


def encode_message(msg: dict) -> bytes:
    """Sérialise un dict en JSON compact + newline → bytes UTF-8.

    Le JSON est écrit sur une seule ligne (separators compacts)
    pour respecter le framing NDJSON.
    """
    line = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
    return (line + "\n").encode("utf-8")


def decode_message(raw: str) -> dict:
    """Parse une ligne JSON (str) en dict Python.

    Raises:
        ValueError: si la chaîne est vide.
        json.JSONDecodeError: si le JSON est malformé.
    """
    stripped = raw.strip()
    if not stripped:
        raise ValueError("Message vide reçu")
    return json.loads(stripped)


def recv_line(conn: socket.socket, buffer: bytearray,
              max_size: int = MAX_MESSAGE_SIZE) -> str | None:
    """Lit le socket octet par octet dans buffer jusqu'à trouver \\n.

    Résout le problème du partial read : accumule les chunks TCP dans
    buffer jusqu'à ce qu'une ligne complète (délimitée par \\n) soit
    disponible.

    Args:
        conn:     Socket connecté.
        buffer:   Buffer persistant entre appels (bytearray mutable).
        max_size: Taille max d'un message (protection DDoS).

    Returns:
        Ligne complète (str, sans \\n) ou None si connexion fermée.

    Raises:
        socket.timeout: si le timeout du socket est dépassé.
        ValueError: si le message dépasse max_size.
    """
    while True:
        # Chercher \\n dans le buffer déjà reçu
        newline_pos = buffer.find(b"\n")
        if newline_pos != -1:
            line = buffer[:newline_pos].decode("utf-8")
            del buffer[:newline_pos + 1]  # consommer la ligne + le \\n
            return line

        # Pas encore de ligne complète → lire plus d'octets
        try:
            chunk = conn.recv(4096)
        except socket.timeout:
            raise  # remonter au caller pour gestion explicite

        if not chunk:
            # Connexion fermée proprement par le pair
            if buffer:
                # Retourner ce qui reste (dernière ligne sans \\n)
                line = buffer[:].decode("utf-8")
                buffer.clear()
                return line if line.strip() else None
            return None

        buffer.extend(chunk)

        if len(buffer) > max_size:
            raise ValueError(f"Message trop volumineux (> {max_size} octets)")
