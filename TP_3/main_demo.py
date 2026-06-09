"""main_demo.py — Démonstration intégrée sans réseau (test local).

Simule le cycle complet serveur/client en local :
  - Encode un IngestRequest → bytes NDJSON
  - Simule la réception côté serveur (buffer)
  - Valide les lectures
  - Encode l'IngestResponse
  - Décode la réponse
  - Affiche le résumé + assertions

Utilité : tester le pipeline complet sans ouvrir de socket réel.
Pour le test réseau réel, utiliser deux terminaux :
    Terminal 1 : python server.py
    Terminal 2 : python client.py
"""
import json
import time
from src.models import SensorReading, IngestRequest, IngestResponse
from src.validators import validate_readings
from src.protocol import encode_message, decode_message, build_message

# ============================================================
# DONNÉES DE TEST
# ============================================================
with open("data/sample_readings.json", encoding="utf-8") as f:
    raw = json.load(f)

readings = [SensorReading.from_dict(r) for r in raw]
ingest_req = IngestRequest(source="station_agricole_01", readings=readings)

print("=" * 60)
print("  DEMO TP3 — Pipeline NDJSON complet (sans réseau)")
print("=" * 60)

# ============================================================
# ÉTAPE 1 : Côté CLIENT — encoder le message
# ============================================================
msg_out = build_message("ingest_request", ingest_req.to_dict())
encoded = encode_message(msg_out)
print(f"\n[CLIENT] Message encodé : {len(encoded)} octets")
print(f"[CLIENT] Aperçu : {encoded[:120].decode()}...")

# ============================================================
# ÉTAPE 2 : Simuler la réception côté SERVEUR (buffer NDJSON)
# ============================================================
buffer = bytearray(encoded)
newline_pos = buffer.find(b"\n")
assert newline_pos != -1, "Pas de \\n dans le message encodé"
line = buffer[:newline_pos].decode("utf-8")
msg_in = decode_message(line)

assert msg_in["type"] == "ingest_request"
assert msg_in["version"] == "v1"
request_id = msg_in["request_id"]
print(f"\n[SERVEUR] Message reçu : type={msg_in['type']} | request_id={request_id[:8]}...")

# ============================================================
# ÉTAPE 3 : Validation des lectures
# ============================================================
start = time.time()
received_req = IngestRequest.from_dict(msg_in["payload"])
accepted, errors = validate_readings(received_req.readings)
elapsed_ms = (time.time() - start) * 1000

print(f"\n[SERVEUR] Validation : {len(accepted)} acceptées, {len(errors)} erreurs")
for e in errors:
    print(f"  ❌ [{e.sensor_id}] {e.field} : {e.message}")

# ============================================================
# ÉTAPE 4 : Construire et encoder la réponse
# ============================================================
response = IngestResponse(
    request_id=request_id,
    accepted_count=len(accepted),
    rejected_count=len(errors),
    errors=errors,
    processing_time_ms=round(elapsed_ms, 3),
)
resp_msg = build_message("ingest_response", response.to_dict(), request_id=request_id)
resp_encoded = encode_message(resp_msg)
print(f"\n[SERVEUR] Réponse encodée : {len(resp_encoded)} octets")

# ============================================================
# ÉTAPE 5 : Côté CLIENT — décoder la réponse
# ============================================================
resp_buffer = bytearray(resp_encoded)
nl = resp_buffer.find(b"\n")
resp_line = resp_buffer[:nl].decode("utf-8")
resp_decoded = decode_message(resp_line)
payload = resp_decoded["payload"]

print(f"\n[CLIENT] Réponse reçue : type={resp_decoded['type']}")
print(f"  ✅ Acceptées    : {payload['accepted_count']}")
print(f"  ❌ Rejetées     : {payload['rejected_count']}")
print(f"  ⏱  Traitement   : {payload['processing_time_ms']} ms")

# ============================================================
# ASSERTIONS
# ============================================================
print("\n--- Vérifications ---")

assert payload["accepted_count"] == 5, f"Attendu 5 acceptées, obtenu {payload['accepted_count']}"
print("[OK] 5 lectures acceptées (temp_01, hum_01, rain_01, irr_02, wind_01)")

assert payload["rejected_count"] == 5, f"Attendu 5 rejetées, obtenu {payload['rejected_count']}"
print("[OK] 5 lectures rejetées")

error_fields = [(e["sensor_id"], e["field"]) for e in payload["errors"]]
assert any(sid == "temp_02" and f == "value" for sid, f in error_fields), "temp_02 non détecté"
print("[OK] temp_02 : valeur aberrante -999 détectée")

assert any(sid == "(inconnu)" and f == "sensor_id" for sid, f in error_fields), "sensor_id vide non détecté"
print("[OK] sensor_id vide détecté")

assert any(sid == "hum_03" and f == "value" for sid, f in error_fields), "hum_03 type str non détecté"
print("[OK] hum_03 : value non numérique détectée")

assert any(sid == "irr_01" and f == "irrigation_mm" for sid, f in error_fields), "irr_01 cohérence non détectée"
print("[OK] irr_01 : incohérence pump OFF + irrigation > 0 détectée")

assert any(sid == "temp_03" and f == "timestamp" for sid, f in error_fields), "temp_03 date invalide non détectée"
print("[OK] temp_03 : timestamp invalide détecté")

# Vérif cycle encode/decode
r1 = SensorReading.from_dict(raw[0])
encoded_r = encode_message(build_message("test", r1.to_dict()))
decoded_r = decode_message(encoded_r.decode("utf-8").strip())
r2 = SensorReading.from_dict(decoded_r["payload"])
assert r1 == r2, "Cycle encode/decode SensorReading échoué"
print("[OK] Cycle encode → decode → reconstruit SensorReading identique")

print("\n✅ Toutes les vérifications passent !")
print("\n💡 Pour le test réseau réel :")
print("   Terminal 1 → python server.py")
print("   Terminal 2 → python client.py")
