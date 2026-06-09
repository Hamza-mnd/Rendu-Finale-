"""models.py — Contrats de messages pour le service d'ingestion IoT (Séance 3)."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SensorReading:
    """Une mesure individuelle d'un capteur IoT."""
    sensor_id: str
    type: str
    value: object          # float attendu, mais peut être invalide à la réception
    unit: str
    timestamp: str
    pump_status: Optional[str] = None
    irrigation_mm: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "sensor_id":    self.sensor_id,
            "type":         self.type,
            "value":        self.value,
            "unit":         self.unit,
            "timestamp":    self.timestamp,
            "pump_status":  self.pump_status,
            "irrigation_mm": self.irrigation_mm,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SensorReading":
        return cls(
            sensor_id=    d.get("sensor_id", ""),
            type=         d.get("type", ""),
            value=        d.get("value"),
            unit=         d.get("unit", ""),
            timestamp=    d.get("timestamp", ""),
            pump_status=  d.get("pump_status"),
            irrigation_mm=d.get("irrigation_mm"),
        )


@dataclass
class ValidationError:
    """Décrit une erreur de validation sur une lecture."""
    sensor_id: str
    field: str
    message: str

    def to_dict(self) -> dict:
        return {"sensor_id": self.sensor_id, "field": self.field, "message": self.message}

    @classmethod
    def from_dict(cls, d: dict) -> "ValidationError":
        return cls(sensor_id=d["sensor_id"], field=d["field"], message=d["message"])


@dataclass
class IngestRequest:
    """Requête d'ingestion contenant plusieurs lectures."""
    source: str
    readings: List[SensorReading]

    def to_dict(self) -> dict:
        return {"source": self.source, "readings": [r.to_dict() for r in self.readings]}

    @classmethod
    def from_dict(cls, d: dict) -> "IngestRequest":
        readings = [SensorReading.from_dict(r) for r in d.get("readings", [])]
        return cls(source=d.get("source", ""), readings=readings)


@dataclass
class IngestResponse:
    """Réponse du serveur après traitement d'une requête d'ingestion."""
    request_id: str
    accepted_count: int
    rejected_count: int
    errors: List[ValidationError] = field(default_factory=list)
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "request_id":        self.request_id,
            "accepted_count":    self.accepted_count,
            "rejected_count":    self.rejected_count,
            "errors":            [e.to_dict() for e in self.errors],
            "processing_time_ms": self.processing_time_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IngestResponse":
        errors = [ValidationError.from_dict(e) for e in d.get("errors", [])]
        return cls(
            request_id=        d["request_id"],
            accepted_count=    d["accepted_count"],
            rejected_count=    d["rejected_count"],
            errors=            errors,
            processing_time_ms=d.get("processing_time_ms", 0.0),
        )
