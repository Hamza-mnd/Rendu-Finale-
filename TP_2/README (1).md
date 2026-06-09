# TP2 – Service d'ingestion IoT (POO, Validation, Sérialisation)

## Objectif

Construire la base logicielle d'un service d'ingestion Big Data IoT en Python.  
Le service reçoit des mesures de capteurs, les valide, les structure via des dataclasses
typées, les sérialise en JSON et trace toutes les opérations dans des logs sécurisés.

---

## Prérequis

- Python 3.10+
- Aucune bibliothèque externe — uniquement la bibliothèque standard (`json`, `logging`, `dataclasses`, `uuid`, `datetime`)

---

## Installation & lancement

```bash
# 1. Aller dans le dossier du projet
cd seance2_ingestion

# 2. Lancer directement (pas de dépendances externes)
python main.py
```

---

## Structure du projet

```
seance2_ingestion/
├── models.py          # Contrats de données (dataclasses)
├── validators.py      # Validateurs polymorphiques
├── main.py            # Point d'entrée — orchestration + vérifications
└── data/
    └── sample_readings.json   # (optionnel) données de référence
```

---

## Architecture

| Fichier | Rôle |
|---|---|
| `models.py` | Définit les 4 dataclasses : `ValidationError`, `SensorReading`, `IngestRequest`, `IngestResponse` |
| `validators.py` | Implémente les validateurs polymorphiques et la fonction `run_validators()` |
| `main.py` | Orchestre le pipeline, configure le logging sécurisé, exécute les assertions |

---

## Contrats de données

### `SensorReading` — mesure d'un capteur

| Champ | Type | Contrainte |
|---|---|---|
| `timestamp` | `str` | Obligatoire, non vide |
| `site_id` | `str` | Obligatoire, non vide |
| `sensor_id` | `str` | Obligatoire, non vide |
| `temperature_c` | `float` | [-50, 60] |
| `humidity_pct` | `float` | [0, 100] |
| `soil_moisture` | `Optional[float]` | [0, 1] si présent |
| `pump_status` | `str` | `'on'` ou `'off'` |
| `irrigation_l_min` | `float` | [0, 50] |

### `IngestResponse` — statuts possibles

| Statut | Signification |
|---|---|
| `ok` | Tous les readings acceptés |
| `partial` | Au moins un accepté, au moins un rejeté |
| `error` | Aucun reading accepté |

---

## Validateurs

| Validateur | Rôle |
|---|---|
| `RequiredFieldsValidator` | Vérifie la présence et non-vacuité des champs obligatoires |
| `RangeValidator` | Vérifie qu'un champ numérique est dans sa plage autorisée |
| `ConsistencyValidator` | Vérifie que si `pump_status='on'` alors `irrigation_l_min > 0` |

Approche **cumulative** : toutes les erreurs sont collectées, jamais d'arrêt à la première.

---

## Anomalies traitées dans les données de test

| Reading | Problème | Code d'erreur |
|---|---|---|
| sensor-02 | `humidity_pct = 150` (hors [0, 100]) | `OUT_OF_RANGE` |
| site-beta #1 | `sensor_id` vide | `EMPTY_FIELD` |
| site-beta #1 | Pompe ON, débit = 0 | `CONSISTENCY_ERROR` |
| sensor-04 | `temperature_c = -60` (hors [-50, 60]) | `OUT_OF_RANGE` |
| sensor-05 | `timestamp` vide | `EMPTY_FIELD` |

---

## Sécurité

- `api_key` masquée dans tous les logs (`****5678`)
- `api_key` exclue de `IngestRequest.to_dict()` (ne transite jamais en clair)
- `sanitize_for_log()` supprime `\n`, `\r`, `\t` pour prévenir les log injections
- Validation à la frontière du service — aucune donnée non validée n'entre dans le système

---

## Résultats

```
5 readings reçus → 1 accepté, 4 rejetés
status : partial
10 assertions passées ✅
```
