"""models.py — Contrats de données pour le service d'ingestion IoT.

Définit les dataclasses qui constituent le contrat de données :
  - ValidationError  : erreur de validation structurée
  - SensorReading    : mesure d'un capteur IoT
  - IngestRequest    : requête d'ingestion (liste de mesures + métadonnées)
  - IngestResponse   : réponse du service (statut, compteurs, erreurs)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ============================================================
# VALIDATION ERROR
# ============================================================
@dataclass(frozen=True)
class ValidationError:
    """Erreur de validation structurée et immuable.

    Attributes:
        field:   Nom du champ concerné.
        code:    Code machine de l'erreur (ex. 'OUT_OF_RANGE').
        message: Message lisible décrivant le problème.
    """
    field: str
    code: str
    message: str

    def to_dict(self) -> dict:
        """Sérialise l'erreur en dictionnaire."""
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }


# ============================================================
# SENSOR READING
# ============================================================
@dataclass
class SensorReading:
    """Mesure d'un capteur IoT — contrat de données entrant.

    Attributes:
        timestamp:        Horodatage ISO 8601 de la mesure.
        site_id:          Identifiant du site (ex. 'site-alpha').
        sensor_id:        Identifiant du capteur (obligatoire, non vide).
        temperature_c:    Température en degrés Celsius.
        humidity_pct:     Humidité relative en pourcentage [0, 100].
        soil_moisture:    Humidité du sol [0, 1] (optionnel).
        pump_status:      État de la pompe : 'on' ou 'off'.
        irrigation_l_min: Débit d'irrigation en litres/minute [0, 50].
    """
    timestamp:        str
    site_id:          str
    sensor_id:        str
    temperature_c:    float
    humidity_pct:     float
    soil_moisture:    Optional[float] = None
    pump_status:      str = "off"
    irrigation_l_min: float = 0.0

    def __post_init__(self):
        """Vérifie les invariants dès la construction."""
        if not self.sensor_id or not self.sensor_id.strip():
            raise ValueError("sensor_id est obligatoire et ne peut pas être vide")

    def to_dict(self) -> dict:
        """Sérialise le SensorReading en dictionnaire JSON-compatible."""
        return {
            "timestamp":        self.timestamp,
            "site_id":          self.site_id,
            "sensor_id":        self.sensor_id,
            "temperature_c":    self.temperature_c,
            "humidity_pct":     self.humidity_pct,
            "soil_moisture":    self.soil_moisture,
            "pump_status":      self.pump_status,
            "irrigation_l_min": self.irrigation_l_min,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SensorReading":
        """Construit un SensorReading depuis un dictionnaire (défensif).

        Les champs inconnus sont ignorés.
        Les champs manquants utilisent des valeurs par défaut sûres.
        """
        return cls(
            timestamp=        str(data.get("timestamp", "")),
            site_id=          str(data.get("site_id", "")),
            sensor_id=        str(data.get("sensor_id", "")),
            temperature_c=    float(data.get("temperature_c", 0.0)),
            humidity_pct=     float(data.get("humidity_pct", 0.0)),
            soil_moisture=    float(data["soil_moisture"]) if data.get("soil_moisture") is not None else None,
            pump_status=      str(data.get("pump_status", "off")).lower(),
            irrigation_l_min= float(data.get("irrigation_l_min", 0.0)),
        )


# ============================================================
# INGEST REQUEST
# ============================================================
@dataclass
class IngestRequest:
    """Requête d'ingestion envoyée par un client IoT.

    Attributes:
        request_id: UUID unique de la requête (pour corrélation et idempotence).
        api_key:    Clé d'authentification (ne doit JAMAIS apparaître dans les logs).
        readings:   Liste des mesures à ingérer.
        sent_at:    Horodatage ISO 8601 d'envoi.
    """
    request_id: str
    api_key:    str
    readings:   List[SensorReading] = field(default_factory=list)
    sent_at:    str = ""

    def to_dict(self) -> dict:
        """Sérialise la requête — api_key EXCLUE (secret)."""
        return {
            "request_id": self.request_id,
            # api_key volontairement omise : ne jamais sérialiser un secret
            "sent_at":    self.sent_at,
            "readings":   [r.to_dict() for r in self.readings],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IngestRequest":
        """Reconstruit une IngestRequest depuis un dictionnaire."""
        readings = [
            SensorReading.from_dict(r)
            for r in data.get("readings", [])
        ]
        return cls(
            request_id= str(data.get("request_id", "")),
            api_key=    str(data.get("api_key", "")),
            readings=   readings,
            sent_at=    str(data.get("sent_at", "")),
        )


# ============================================================
# INGEST RESPONSE
# ============================================================
@dataclass
class IngestResponse:
    """Réponse du service d'ingestion.

    Attributes:
        status:          'ok' | 'partial' | 'error'
        accepted_count:  Nombre de readings acceptés.
        rejected_count:  Nombre de readings rejetés.
        errors:          Liste des erreurs de validation rencontrées.
    """
    status:         str
    accepted_count: int = 0
    rejected_count: int = 0
    errors:         List[ValidationError] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Sérialise la réponse en dictionnaire JSON-compatible."""
        return {
            "status":          self.status,
            "accepted_count":  self.accepted_count,
            "rejected_count":  self.rejected_count,
            "errors":          [e.to_dict() for e in self.errors],
        }
