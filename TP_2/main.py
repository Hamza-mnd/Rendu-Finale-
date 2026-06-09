"""main.py — Point d'entrée du service d'ingestion IoT (TP Séance 2).

Orchestre le traitement complet :
  1. Configuration du logging sécurisé
  2. Définition des validateurs
  3. Traitement des readings (validation + construction + réponse)
  4. Affichage de la réponse JSON
  5. Assertions de vérification
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from models import SensorReading, IngestRequest, IngestResponse, ValidationError
from validators import (
    Validator, RangeValidator, ConsistencyValidator,
    RequiredFieldsValidator, run_validators,
)

# ============================================================
# CONFIGURATION DU LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingestion")


# ============================================================
# SÉCURITÉ : SANITIZATION & MASQUAGE
# ============================================================
def sanitize_for_log(value: str, max_len: int = 200) -> str:
    """Supprime les caractères dangereux pour le log (anti log-injection).

    Supprime \\n, \\r, \\t et tronque à max_len caractères.

    Args:
        value:   Chaîne à sanitizer.
        max_len: Longueur maximale autorisée.

    Returns:
        Chaîne nettoyée et tronquée si nécessaire.
    """
    sanitized = value.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    if len(sanitized) > max_len:
        return sanitized[:max_len] + "...[TRONQUÉ]"
    return sanitized


def mask_api_key(key: str) -> str:
    """Masque une clé API pour le logging sécurisé.

    Retourne '****' + les 4 derniers caractères si la clé fait ≥ 8 chars,
    sinon '****'.

    Args:
        key: Clé API à masquer.

    Returns:
        Clé masquée (ex. '****5678').
    """
    if len(key) >= 8:
        return "****" + key[-4:]
    return "****"


# ============================================================
# DÉFINITION DES VALIDATEURS
# ============================================================
VALIDATORS: list[Validator] = [
    RequiredFieldsValidator(["timestamp", "site_id", "sensor_id"]),
    RangeValidator("temperature_c",    -50.0, 60.0),
    RangeValidator("humidity_pct",       0.0, 100.0),
    RangeValidator("soil_moisture",      0.0, 1.0),
    RangeValidator("irrigation_l_min",   0.0, 50.0),
    ConsistencyValidator(),
]


# ============================================================
# DONNÉES DE TEST
# ============================================================
sample_readings_raw = [
    # ✅ Reading valide
    {"timestamp": "2026-02-16T08:00:00Z", "site_id": "site-alpha",
     "sensor_id": "sensor-01", "temperature_c": 22.5, "humidity_pct": 65.0,
     "soil_moisture": 0.42, "pump_status": "off", "irrigation_l_min": 0.0},
    # ❌ humidity_pct = 150 (hors [0, 100])
    {"timestamp": "2026-02-16T08:05:00Z", "site_id": "site-alpha",
     "sensor_id": "sensor-02", "temperature_c": 23.1, "humidity_pct": 150.0,
     "soil_moisture": 0.38, "pump_status": "off", "irrigation_l_min": 0.0},
    # ❌ sensor_id vide + pompe ON sans débit
    {"timestamp": "2026-02-16T08:10:00Z", "site_id": "site-beta",
     "sensor_id": "", "temperature_c": 19.8, "humidity_pct": 70.2,
     "soil_moisture": 0.55, "pump_status": "on", "irrigation_l_min": 0.0},
    # ❌ temperature_c = -60 (hors [-50, 60])
    {"timestamp": "2026-02-16T08:15:00Z", "site_id": "site-beta",
     "sensor_id": "sensor-04", "temperature_c": -60.0, "humidity_pct": 72.0,
     "soil_moisture": 0.60, "pump_status": "on", "irrigation_l_min": 3.5},
    # ❌ timestamp vide
    {"timestamp": "", "site_id": "site-gamma", "sensor_id": "sensor-05",
     "temperature_c": 25.0, "humidity_pct": 55.0, "soil_moisture": None,
     "pump_status": "off", "irrigation_l_min": 0.0},
]


# ============================================================
# TRAITEMENT PRINCIPAL
# ============================================================
def process_ingestion(raw_readings: list, api_key: str) -> IngestResponse:
    """Traite une requête d'ingestion complète.

    Pour chaque reading :
      1. Validation sur le dict brut (tous les validateurs)
      2. Si valide → construction de l'objet SensorReading
      3. Sinon → rejet et collecte des erreurs

    Args:
        raw_readings: Liste de dicts bruts reçus du client.
        api_key:      Clé API du client (masquée dans les logs).

    Returns:
        IngestResponse avec statut, compteurs et liste d'erreurs.
    """
    request_id = str(uuid.uuid4())
    logger.info(
        "Requête reçue | request_id=%s | api_key=%s | nb_readings=%d",
        request_id, mask_api_key(api_key), len(raw_readings)
    )

    accepted: list[SensorReading] = []
    all_errors: list[ValidationError] = []

    for i, raw in enumerate(raw_readings):
        sid = sanitize_for_log(str(raw.get("sensor_id", "?")))

        # Étape 1 : validation cumulative sur le dict brut
        errors = run_validators(raw, VALIDATORS)

        if errors:
            logger.warning(
                "  Reading #%d (sensor=%s) : %d erreur(s)", i, sid, len(errors)
            )
            for e in errors:
                logger.warning("    -> [%s] %s : %s", e.code, e.field, e.message)
                all_errors.append(e)
        else:
            # Étape 2 : construction de l'objet (peut lever ValueError)
            try:
                reading = SensorReading.from_dict(raw)
                accepted.append(reading)
                logger.info("  Reading #%d (sensor=%s) : ACCEPTÉ", i, sid)
            except (ValueError, TypeError) as exc:
                err = ValidationError("__construction__", "BUILD_ERROR", str(exc))
                all_errors.append(err)
                logger.warning(
                    "  Reading #%d (sensor=%s) : REJETÉ à la construction : %s",
                    i, sid, exc
                )

    # Construction de la réponse
    rejected_count = len(raw_readings) - len(accepted)
    if rejected_count == 0:
        status = "ok"
    elif len(accepted) > 0:
        status = "partial"
    else:
        status = "error"

    response = IngestResponse(
        status=status,
        accepted_count=len(accepted),
        rejected_count=rejected_count,
        errors=all_errors,
    )
    logger.info(
        "Réponse | request_id=%s | status=%s | accepted=%d | rejected=%d",
        request_id, response.status, response.accepted_count, response.rejected_count
    )
    return response


# ============================================================
# POINT D'ENTRÉE
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  SERVICE D'INGESTION IoT — Séance 2 (TP)")
    print("=" * 60)

    result = process_ingestion(sample_readings_raw, api_key="sk-secret-key-12345678")

    print("\n--- Réponse (JSON) ---")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    # ============================================================
    # VÉRIFICATIONS (ASSERTIONS)
    # ============================================================
    print("\n--- Vérifications ---")

    # 1. Sérialisation aller-retour SensorReading
    valid_data = sample_readings_raw[0]
    r1 = SensorReading.from_dict(valid_data)
    r2 = SensorReading.from_dict(r1.to_dict())
    assert r1 == r2, "Échec : sérialisation aller-retour"
    print("[OK] Sérialisation aller-retour SensorReading")

    # 2. JSON aller-retour complet
    json_str = json.dumps(r1.to_dict())
    r3 = SensorReading.from_dict(json.loads(json_str))
    assert r1 == r3, "Échec : cycle JSON complet"
    print("[OK] Cycle JSON complet (to_dict → json.dumps → json.loads → from_dict)")

    # 3. sensor_id vide lève ValueError
    try:
        SensorReading.from_dict({
            "timestamp": "t", "site_id": "s", "sensor_id": "",
            "temperature_c": 20, "humidity_pct": 50
        })
        assert False, "Aurait dû lever ValueError"
    except ValueError:
        print("[OK] sensor_id vide lève ValueError")

    # 4. humidity hors plage → OUT_OF_RANGE
    errs = run_validators(sample_readings_raw[1], VALIDATORS)
    assert any(e.code == "OUT_OF_RANGE" and e.field == "humidity_pct" for e in errs), \
        "humidity_pct=150 non détectée comme OUT_OF_RANGE"
    print("[OK] humidity_pct=150 détectée comme OUT_OF_RANGE")

    # 5. sensor_id vide → EMPTY_FIELD + pompe ON sans débit → CONSISTENCY_ERROR
    errs3 = run_validators(sample_readings_raw[2], VALIDATORS)
    assert any(e.code == "EMPTY_FIELD" and e.field == "sensor_id" for e in errs3), \
        "sensor_id vide non détecté"
    assert any(e.code == "CONSISTENCY_ERROR" for e in errs3), \
        "Incohérence pompe/débit non détectée"
    print("[OK] sensor_id vide + incohérence pompe/débit détectées (2 erreurs)")

    # 6. temperature hors plage → OUT_OF_RANGE
    errs4 = run_validators(sample_readings_raw[3], VALIDATORS)
    assert any(e.code == "OUT_OF_RANGE" and e.field == "temperature_c" for e in errs4), \
        "temperature_c=-60 non détectée"
    print("[OK] temperature_c=-60 détectée comme OUT_OF_RANGE")

    # 7. Masquage API key
    assert mask_api_key("sk-abcdef1234") == "****1234", "Masquage incorrect"
    assert mask_api_key("short") == "****", "Masquage clé courte incorrect"
    print("[OK] mask_api_key fonctionne")

    # 8. Sanitization log injection
    malicious = "sensor-01\nERROR: system hacked"
    sanitized = sanitize_for_log(malicious)
    assert "\n" not in sanitized, "Log injection non bloquée"
    print("[OK] sanitize_for_log bloque les sauts de ligne")

    # 9. IngestRequest sérialisation (api_key exclue)
    req = IngestRequest(
        request_id=str(uuid.uuid4()),
        api_key="sk-secret-key-12345678",
        readings=[r1],
        sent_at=datetime.now(timezone.utc).isoformat(),
    )
    req_dict = req.to_dict()
    assert "api_key" not in req_dict, "api_key ne doit PAS apparaître dans to_dict()"
    print("[OK] api_key absente de IngestRequest.to_dict()")

    # 10. Résultat global : 1 accepté sur 5
    assert result.accepted_count == 1, f"Attendu 1 accepté, obtenu {result.accepted_count}"
    assert result.rejected_count == 4, f"Attendu 4 rejetés, obtenu {result.rejected_count}"
    assert result.status == "partial"
    print("[OK] Résultat global : 1 accepté, 4 rejetés, status='partial'")

    print("\n✅ Toutes les vérifications sont passées !")
