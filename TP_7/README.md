# Séance 7 — Mini broker partitionné avec consumers et offsets

> **Module** : Applications Distribuées — Parcours Big Data  
> **Durée** : 240 min | **Public** : 1ère année Big Data | **Langage** : Python 3.11+

---

## Lancement rapide (VS Code)

### Option A — Bouton ▶ Run Python File
1. Ouvre le dossier `seance7/` dans VS Code (`File > Open Folder`)
2. Ouvre `run.py`
3. Clique sur **▶** en haut à droite (ou `Ctrl+F5`)

### Option B — Débogage avec paramètres (F5)
1. Va dans l'onglet **Run and Debug** (`Ctrl+Shift+D`)
2. Choisis une configuration dans le menu déroulant :
   - `Séance 7 — run par défaut` : 4 partitions, 2 consumers, 30 s
   - `Séance 7 — skew (clé site_id)` : observe le déséquilibre de charge
   - `Séance 7 — consumer lent (lag visible)` : observe le backlog qui grossit
3. Appuie sur **F5**

### Option C — Terminal intégré VS Code
```bash
# Depuis le dossier seance7/
python run.py
python run.py --partitions 6 --consumers 3 --duration 60
```

---

## Arborescence du projet

```
seance7/
├── run.py                  ← point d'entrée VS Code  ← LANCER ICI
├── README.md
├── .vscode/
│   └── launch.json         ← configurations F5
├── src/
│   ├── __init__.py
│   ├── events.py           ← dataclass Event + générateur aléatoire
│   ├── partitioner.py      ← routage SHA-256 → partition N
│   ├── broker.py           ← broker en mémoire, N partitions indépendantes
│   ├── consumers.py        ← consumer group, assignation round-robin, workers
│   ├── offsets.py          ← OffsetStore thread-safe + commit atomique disque
│   ├── storage.py          ← écriture JSONL partitionnée (style Hive)
│   ├── metrics.py          ← backlog, lag, throughput fenêtre glissante
│   └── main.py             ← orchestrateur + argparse
├── outputs/                ← données produites (créé automatiquement)
│   └── date=YYYY-MM-DD/
│       └── site=SITE-XX/
│           └── partition=N/
│               └── events.jsonl
├── logs/                   ← logs d'exécution (créé automatiquement)
│   └── run.log
└── state/                  ← offsets persistants (créé automatiquement)
    └── offsets.json
```

---

## Prérequis

- **Python 3.11+**
- **Aucune dépendance externe** — bibliothèque standard uniquement
- VS Code avec l'extension **Python** (Microsoft)

---

## Options de lancement

| Option | Défaut | Description |
|---|---|---|
| `--partitions` | 4 | Nombre de partitions |
| `--consumers` | 2 | Nombre de consumers dans le groupe |
| `--key-field` | `sensor_id` | Champ utilisé comme clé de partition |
| `--producer-rate` | 50 | Délai producteur en millisecondes |
| `--consumer-delay` | 30 | Délai de traitement simulé par événement (ms) |
| `--commit-every` | 5 | Fréquence de commit des offsets (nb messages) |
| `--duration` | 30 | Durée totale d'exécution (secondes) |
| `--group` | `agri-stats` | Nom du consumer group |

---

## Architecture

```
                    ┌─────────────────────────────────┐
                    │           BROKER                 │
 Producteur ──────▶ │  partition 0  │  partition 1    │
 (thread)           │  partition 2  │  partition 3    │
                    └─────────────────────────────────┘
                           │              │
                    ┌──────┘              └──────┐
                    ▼                            ▼
              Consumer C0                  Consumer C1
           (partitions 0, 2)           (partitions 1, 3)
                    │                            │
             OffsetStore ◀──── state/offsets.json
                    │
               Storage
    outputs/date=.../site=.../partition=N/events.jsonl
```

### Règle fondamentale des consumer groups

> **Une partition ne peut être lue que par un seul consumer à la fois au sein du même groupe.**

| Situation | Résultat |
|---|---|
| `consumers < partitions` | Certains consumers traitent plusieurs partitions |
| `consumers == partitions` | Assignation 1-pour-1, parallélisme maximal |
| `consumers > partitions` | Des consumers restent inactifs |

---

## Mécanisme des offsets

```
Partition 0 :  [evt0] [evt1] [evt2] [evt3] [evt4] ...
                                    ▲
                              offset=3 (commité dans state/offsets.json)
```

- L'offset progresse **en mémoire** entre deux commits (`set_memory`).
- Toutes les N lectures (`--commit-every`), il est **persisté atomiquement** sur disque.
- Au redémarrage, le consumer reprend depuis le dernier offset commité → **at-least-once**.

---

## Format des données produites

Chaque fichier `events.jsonl` contient un événement JSON par ligne :

```json
{"event_id": "e-a1b2c3d4", "sensor_id": "sensor-03", "site_id": "SITE-01", "event_time": "2026-04-20T08:00:05", "temperature_c": 23.7, "humidity_pct": 57.2}
```

La hiérarchie `date= / site= / partition=` reproduit le **partitionnement Hive** des data lakes (compatible Spark, DuckDB, pandas).

---

## Tester les modules individuellement

```bash
# Tester la distribution des partitions (uniforme vs skew)
python -m src.partitioner

# Tester la génération d'événements
python -m src.events
```

---

## Concepts clés

| Concept | Module | Description |
|---|---|---|
| Partitionnement | `partitioner.py` | SHA-256 → distribution uniforme |
| Hotspot / Skew | `partitioner.py` | Clé sur-représentée → partition surchargée |
| Consumer group | `consumers.py` | Assignation round-robin, parallélisme |
| Offset | `offsets.py` | Curseur de lecture par partition |
| At-least-once | `offsets.py` | Commit périodique → possible rejeu |
| Persistance partitionnée | `storage.py` | Hive-style, compatible data lake |
| Backlog / Lag | `metrics.py` | Distance producteur ↔ consumer |

---

## Préparation Séance 8

À l'issue de cette séance vous devriez pouvoir :

- [ ] Expliquer pourquoi Kafka utilise le partitionnement pour scaler.
- [ ] Décrire ce qui se passe lors d'un rebalancing de consumer group.
- [ ] Calculer le lag d'un pipeline à partir des offsets et de la taille des partitions.
- [ ] Lire un fichier JSONL partitionné avec DuckDB ou pandas.

La séance 8 introduira le **fenêtrage temporel** et le **stream processing stateful**.
