"""rpc_protocol.py — Construction et validation des messages RPC (Séance 4)."""
import json
import uuid
import time
from typing import Any

MAX_PAYLOAD_SIZE = 1_000_000  # 1 Mo


def build_request(method: str, params: dict = None) -> dict:
    """Construit un message RPC Request complet."""
    return {
        "rpc_version": "1.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params or {},
        "sent_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def build_response(rpc_id: str, result: Any) -> dict:
    """Construit une réponse RPC de succès."""
    return {
        "rpc_version": "1.0",
        "id": rpc_id,
        "result": result,
        "error": None,
    }


def build_error_response(rpc_id: str, code: int, message: str,
                          details: str = "") -> dict:
    """Construit une réponse RPC d'erreur."""
    return {
        "rpc_version": "1.0",
        "id": rpc_id or "",
        "result": None,
        "error": {"code": code, "message": message, "details": details},
    }


def validate_rpc_request(raw_bytes: bytes) -> tuple[dict | None, dict | None]:
    """Valide le body brut d'une requête RPC.

    Returns:
        (parsed_request, None) si valide.
        (None, error_response) si invalide.
    """
    # 1. Taille maximale
    if len(raw_bytes) > MAX_PAYLOAD_SIZE:
        return None, build_error_response(
            "", 1002, "Payload too large",
            f"Max {MAX_PAYLOAD_SIZE} bytes, reçu {len(raw_bytes)}"
        )

    # 2. Parse JSON
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, build_error_response("", -32700, "Parse error", str(e))

    # 3. Doit être un objet JSON
    if not isinstance(data, dict):
        return None, build_error_response(
            "", -32600, "Invalid request", "Body must be a JSON object"
        )

    # 4. Champs obligatoires
    rpc_id = data.get("id", "")
    for field_name in ("id", "method"):
        if field_name not in data or not data[field_name]:
            return None, build_error_response(
                rpc_id, -32600, "Invalid request",
                f"Champ obligatoire absent ou vide : '{field_name}'"
            )

    if not isinstance(data["method"], str):
        return None, build_error_response(
            rpc_id, -32600, "Invalid request",
            "Le champ 'method' doit être une chaîne de caractères"
        )

    return data, None
