"""models.py — Dataclasses pour le service RPC IoT (Séance 4)."""
from dataclasses import dataclass, field, asdict
from typing import Any
import uuid
import time


@dataclass
class SensorReading:
    """Mesure individuelle d'un capteur IoT."""
    sensor_id: str
    ts: str
    value: Any  # float attendu, peut être invalide à la réception

    def validate(self) -> list[str]:
        """Valide la lecture. Retourne la liste des erreurs (vide = OK)."""
        errors = []
        if not self.sensor_id or not str(self.sensor_id).strip():
            errors.append("sensor_id est vide")
        if not self.ts or not str(self.ts).strip():
            errors.append("ts est vide")
        if isinstance(self.value, bool):
            errors.append(f"value n'est pas numérique : {self.value}")
        elif not isinstance(self.value, (int, float)):
            errors.append(f"value n'est pas numérique : {repr(self.value)}")
        elif abs(self.value) > 1000:
            errors.append(f"value aberrante : {self.value}")
        return errors


@dataclass
class RpcError:
    """Erreur RPC structurée."""
    code: int
    message: str
    details: str = ""


@dataclass
class RpcRequest:
    """Message de requête RPC."""
    method: str
    params: dict = field(default_factory=dict)
    rpc_version: str = "1.0"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sent_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RpcResponse:
    """Message de réponse RPC."""
    id: str
    result: Any = None
    error: dict | None = None
    rpc_version: str = "1.0"

    def to_dict(self) -> dict:
        return asdict(self)
