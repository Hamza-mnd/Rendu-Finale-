# TP5 – Pipeline asynchrone d'ingestion IoT

## Objectif

Construire un pipeline complet producteur → file → workers → stockage en Python pur,
avec retry, dead-letter queue, backpressure et métriques d'observabilité.

---

## Prérequis

- Python 3.11+
- Aucune bibliothèque externe

---

## Lancement

```bash
cd seance5_pipeline
python -m src.main
```

---

## Structure du projet

```
seance5_pipeline/
├── src/
│   ├── __init__.py
│   ├── messages.py    # EventMessage (dataclass enveloppe)
│   ├── producers.py   # Générateur de rafales IoT
│   ├── workers.py     # Validation + traitement + retry/DLQ
│   ├── metrics.py     # PipelineMetrics + dashboard
│   ├── storage.py     # CSVStorage thread-safe + agrégation
│   ├── pipeline.py    # Queue principale + DLQ + stop_event
│   └── main.py        # Orchestration complète
├── logs/
│   └── pipeline.log         # Journal d'exécution
└── outputs/
    ├── valid_readings.csv   # Lectures valides
    ├── dead_letters.json    # Messages échoués après max retries
    └── aggregation.json     # Résumé par capteur
```

---

## Architecture du pipeline

```
Prod-1 ──┐
Prod-2 ──┼──▶ Queue(maxsize=50) ──▶ Worker-1 ──▶ CSVStorage
Prod-3 ──┘         │                Worker-2 ──▶ Métriques
                   │                   │
              backpressure          DLQ (échecs)
              (drop si plein)
```

---

## Paramètres

| Paramètre | Valeur |
|---|---|
| Producteurs | 3 |
| Workers initiaux | 2 (+ scale-out jusqu'à 5) |
| Taille queue | 50 (backpressure) |
| Bursts par producteur | 5 × 30 messages |
| Taux d'invalides | ~10 % |
| Max retries | 3 |

---

## Logique retry / DLQ

| Situation | Action |
|---|---|
| Validation OK | Écriture CSV + compteur succès |
| Validation KO + `attempts < max_attempts` | Remise en queue (retry) |
| Validation KO + `attempts == max_attempts` | → Dead-Letter Queue |
| Queue pleine au moment du retry | → Dead-Letter Queue directement |

---

## Observabilité — Dashboard

```
[DASHBOARD] backlog=  47 | success=  89 | fail=  2 | retry= 11 | rate=  38.2 msg/s | latency= 1205.7ms
```

| Indicateur | Signification |
|---|---|
| `backlog` | Messages en attente (monte si λ > μ) |
| `success` | Messages traités avec succès |
| `fail` | Messages en DLQ |
| `retry` | Tentatives de re-traitement |
| `rate` | Débit de traitement (msg/s) |
| `latency` | Temps moyen dans le pipeline |

---

## Résultats obtenus

```
450 messages produits (3 × 5 × 30)
413 acceptés | 37 en DLQ | 74 retries
Débit : ~69 msg/s | Durée : ~6s
✅ Toutes les assertions passent
```
