"""validators.py — Validation métier des lectures IoT (Séance 3).

Règles :
  - sensor_id   : obligatoire, non vide
  - value       : doit être numérique (float/int)
  - timestamp   : doit contenir 'T' (format ISO 8601 basique)
  - temperature : value dans [-50, 60]
  - humidity    : value dans [0, 100]
  - pump OFF    : irrigation_mm doit être None ou 0
"""
from typing import List, Tuple
from src.models import SensorReading, ValidationError

# Plages par type de capteur
RANGE_RULES = {
    "temperature": (-50.0, 60.0),
    "humidity":    (0.0, 100.0),
}


def validate_reading(r: SensorReading) -> List[ValidationError]:
    """Valide une lecture — retourne la liste des erreurs (vide = OK)."""
    errors: List[ValidationError] = []
    sid = r.sensor_id or "(inconnu)"

    # 1. sensor_id obligatoire
    if not r.sensor_id or not r.sensor_id.strip():
        errors.append(ValidationError(
            sensor_id="(inconnu)", field="sensor_id",
            message="sensor_id est obligatoire et ne peut pas être vide."
        ))

    # 2. value doit être numérique
    try:
        numeric_value = float(r.value)
    except (TypeError, ValueError):
        errors.append(ValidationError(
            sensor_id=sid, field="value",
            message=f"value doit être numérique, reçu : {repr(r.value)}"
        ))
        numeric_value = None

    # 3. Plage selon le type
    if numeric_value is not None and r.type in RANGE_RULES:
        low, high = RANGE_RULES[r.type]
        if not (low <= numeric_value <= high):
            errors.append(ValidationError(
                sensor_id=sid, field="value",
                message=f"value={numeric_value} hors plage [{low}, {high}] pour type '{r.type}'."
            ))

    # 4. Timestamp : doit contenir 'T' (ISO 8601 basique)
    if not r.timestamp or "T" not in r.timestamp:
        errors.append(ValidationError(
            sensor_id=sid, field="timestamp",
            message=f"timestamp invalide ou absent : {repr(r.timestamp)}"
        ))

    # 5. Cohérence pompe : pump OFF → irrigation_mm doit être 0 ou None
    if r.pump_status and r.pump_status.upper() == "OFF":
        if r.irrigation_mm is not None and float(r.irrigation_mm) > 0:
            errors.append(ValidationError(
                sensor_id=sid, field="irrigation_mm",
                message=f"pump_status=OFF mais irrigation_mm={r.irrigation_mm} > 0."
            ))

    return errors


def validate_readings(
    readings: List[SensorReading],
) -> Tuple[List[SensorReading], List[ValidationError]]:
    """Valide toutes les lectures.

    Returns:
        (accepted, all_errors) — listes des lectures valides et de toutes les erreurs.
    """
    accepted: List[SensorReading] = []
    all_errors: List[ValidationError] = []

    for r in readings:
        errs = validate_reading(r)
        if errs:
            all_errors.extend(errs)
        else:
            accepted.append(r)

    return accepted, all_errors
