# TP3 – Mini service d'ingestion IoT sur sockets TCP

## Objectif

Construire un service distribué client/serveur en Python pur (bibliothèque standard uniquement).  
Le serveur TCP reçoit des mesures IoT encodées en NDJSON, les valide et renvoie un bilan détaillé au client.

---

## Prérequis

- Python 3.11+
- Aucune bibliothèque externe

---

## Lancement

### Option 1 — Démo intégrée (sans réseau, recommandée pour tester)

```bash
cd seance3_ingestion
python main_demo.py
```

### Option 2 — Test réseau réel (2 terminaux)

```bash
# Terminal 1 — démarrer le serveur
cd seance3_ingestion
python src/server.py

# Terminal 2 — lancer le client
cd seance3_ingestion
python src/client.py
```

Options disponibles :
```bash
python src/server.py --host 127.0.0.1 --port 9000
python src/client.py --host 127.0.0.1 --port 9000 --file data/sample_readings.json
```

---

## Structure du projet

```
seance3_ingestion/
├── main_demo.py          # Démo intégrée (pipeline complet sans socket réel)
├── data/
│   └── sample_readings.json   # 10 lectures IoT (5 valides, 5 avec erreurs)
├── logs/                 # Logs générés à l'exécution
├── outputs/              # Résultats JSON sauvegardés
└── src/
    ├── __init__.py
    ├── models.py         # Dataclasses : SensorReading, IngestRequest, IngestResponse
    ├── validators.py     # Validation métier (plages, types, cohérence)
    ├── protocol.py       # Framing NDJSON : encode, decode, recv_line
    ├── server.py         # Serveur TCP
    └── client.py         # Client TCP
```

---

## Protocole applicatif (v1)

| Champ | Valeur |
|---|---|
| Format | JSON compact, une ligne, terminé par `\n` (NDJSON) |
| `version` | `"v1"` |
| `type` | `ingest_request` / `ingest_response` / `ping` / `error` |
| `request_id` | UUID v4 (corrélation logs + idempotence) |
| `sent_at` | ISO 8601 |
| `payload` | Données métier (IngestRequest ou IngestResponse) |

---

## Erreurs traitées dans les données de test

| Capteur | Erreur | Code détecté |
|---|---|---|
| `temp_02` | `value = -999.0` (hors [-50, 60]) | `OUT_OF_RANGE` |
| *(vide)* | `sensor_id` vide | `MISSING_FIELD` |
| `hum_03` | `value = "haute"` (non numérique) | `INVALID_TYPE` |
| `irr_01` | `pump=OFF` mais `irrigation_mm=5.2` | `CONSISTENCY_ERROR` |
| `temp_03` | `timestamp = "not-a-date"` | `INVALID_TIMESTAMP` |

---

## Résultats

```
10 lectures → 5 acceptées, 5 rejetées
Toutes les assertions passent ✅
```
