# TP4 – Mini RPC Data Service (Ingestion + Stats)

## Objectif

Construire un service RPC complet en Python pur sur HTTP : routeur de méthodes,
validation, threading, métriques et logs structurés JSON.

---

## Prérequis

- Python 3.11+
- Aucune bibliothèque externe

---

## Lancement

### Option 1 — Démo intégrée (sans réseau)

```bash
cd rpc_data_service
python cli.py --demo
```

### Option 2 — Mode réseau réel (2 terminaux)

```bash
# Terminal 1
python server.py

# Terminal 2
python cli.py ping
python cli.py ingest
python cli.py stats --date 2026-03-09
python cli.py top --n 3
```

---

## Structure du projet

```
rpc_data_service/
├── cli.py                  # Démo intégrée + interface CLI
├── logs/
│   └── server.log          # Logs JSON structurés (généré à l'exécution)
├── outputs/
│   ├── ingested_data.csv   # Export CSV des lectures acceptées
│   └── run_report.json     # Rapport de métriques
└── src/
    ├── __init__.py
    ├── models.py            # Dataclasses : SensorReading, RpcRequest, RpcResponse
    ├── rpc_protocol.py      # build_request / build_response / validate_rpc_request
    ├── router.py            # MethodRouter — registry + dispatch
    ├── services.py          # Logique métier + DataStore thread-safe
    ├── server.py            # ThreadingHTTPServer + RPCHandler
    ├── client.py            # RpcClient avec timeout + retry + backoff
    └── observability.py     # StructuredLogger JSON + MetricsCollector
```

---

## Méthodes RPC disponibles

| Méthode | Params | Résultat |
|---|---|---|
| `health.ping` | `{}` | `{status, ts}` |
| `ingest.batch` | `{readings: [...]}` | `{accepted, rejected, errors}` |
| `stats.daily_summary` | `{date: "YYYY-MM-DD"}` | `{count, avg, min, max}` |
| `stats.top_sensors` | `{n: 5}` | `{sensors: [{sensor_id, avg}]}` |

---

## Codes d'erreur RPC

| Code | Signification |
|---|---|
| `-32700` | Parse error (JSON invalide) |
| `-32600` | Invalid request (champs manquants) |
| `-32601` | Method not found |
| `-32602` | Invalid params |
| `-32603` | Internal error (retriable) |
| `1002` | Payload too large |

---

## Erreurs traitées dans les données de test

| Index | Erreur | Détection |
|---|---|---|
| 3 | `sensor_id` vide | `SensorReading.validate()` |
| 5 | `value = "abc"` non numérique | `isinstance` check |
| 7 | `ts` vide | `SensorReading.validate()` |
| 8 | `value = 9999.9` aberrant | `abs(value) > 1000` |

---

## Résultats

```
10 lectures → 6 acceptées, 4 rejetées
avg = 17.63 | min = -5.1 | max = 25.3
Toutes les vérifications passent ✅
```
