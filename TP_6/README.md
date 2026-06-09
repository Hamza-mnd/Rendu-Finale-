# TP6 – Mini Stream Processor IoT

## Objectif

Construire un pipeline streaming complet en Python pur :
fenêtres tumbling, keyed state, watermark, lateness, checkpoint et observabilité.

---

## Prérequis

- Python 3.11+
- Aucune bibliothèque externe

---

## Lancement

```bash
cd seance6_stream
python src/main.py
```

---

## Structure du projet

```
seance6_stream/
├── data/
│   └── events.json          # 13 événements IoT (dont out-of-order et invalides)
├── src/
│   ├── __init__.py
│   ├── events.py            # Dataclass Event + parsing ISO → epoch
│   ├── source.py            # EventSource (thread daemon, sentinel)
│   ├── processor.py         # StreamProcessor : keyed state, watermark, flush
│   ├── checkpoint.py        # save / load état JSON
│   ├── sink.py              # Export CSV, JSON, rapport run
│   ├── metrics.py           # Dashboard : throughput, latence, backlog
│   └── main.py              # Orchestration complète
├── checkpoints/
│   └── state.json           # Checkpoint périodique (généré à l'exécution)
├── logs/
│   └── pipeline.log         # Logs structurés
└── outputs/
    ├── aggregates.csv        # Agrégats par (sensor_id, window)
    ├── late_events.json      # Événements acceptés en retard
    ├── dropped_events.json   # Événements too-late (dropped)
    └── run_report.json       # Rapport de session
```

---

## Architecture du pipeline

```
data/events.json
      ↓
 EventSource (thread)
      ↓ queue.Queue(maxsize=50)
 StreamProcessor
   ├── watermark = max(event_time) - 5s
   ├── keyed state : dict[(sensor_id, window_start)] → WindowState
   ├── flush_closed_windows() après chaque événement
   └── lateness policy : accept / late / dropped
      ↓
 Sink : CSV + JSON + rapport
```

---

## Fenêtres tumbling (60s)

Chaque événement est assigné à une fenêtre via :
```python
window_start = int(event_time // 60) * 60
```

---

## Politique de lateness

| Situation | Action |
|---|---|
| `watermark <= window_end` | On-time → accepté normalement |
| `watermark > window_end` et `lateness <= 120s` | Late-accepted |
| `watermark > window_end` et `lateness > 120s` | Dropped (too-late) |

---

## Cas spéciaux des données de test

| Événement | Situation | Résultat |
|---|---|---|
| evt-007 (10:00:15) | Arrive après evt-005 (10:01:10) | Late-accepted (20s) |
| evt-009 (10:00:08) | Arrive après evt-005 (10:01:10) | Late-accepted (35s) |
| evt-011 (09:55:00) | Arrive très tard | **Dropped** (360s > 120s) |
| evt-012 (soil_moisture="N/A") | Valeur invalide | soil_moisture=None |

---

## Résultats obtenus

```
13 événements traités → 10 fenêtres flushées
Late acceptés : 2 | Dropped : 1 (evt-011)
✅ Toutes les assertions passent
```
