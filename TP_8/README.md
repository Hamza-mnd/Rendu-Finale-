# Séance 8 — Plateforme distribuée de suivi de commandes et livraisons

> **Module** : Applications Distribuées — Parcours Big Data  
> **Durée** : 240 min | **Public** : 1ère année Big Data | **Langage** : Python 3.11+

---

## Lancement rapide (VS Code)

1. `File > Open Folder` → sélectionne le dossier `livraison_platform/`
2. Ouvre `run.py`
3. Clique sur **▶** ou appuie sur **F5**

---

## Arborescence

```
livraison_platform/
├── run.py                        ← LANCER ICI (VS Code ▶)
├── main.py                       ← orchestrateur complet
├── README.md
├── rapport_final.json            ← généré à l'exécution
├── .vscode/
│   └── launch.json               ← config F5
│
├── contracts/                    ← Sous-partie B
│   ├── order.py                  ← dataclass Order + validate_order()
│   └── event.py                  ← dataclass OrderEvent + validate_event()
│
├── service/                      ← Sous-partie C
│   └── order_service.py          ← service synchrone de prise de commande
│
├── broker/                       ← Sous-parties D & E
│   └── mini_broker.py            ← broker en mémoire, 4 partitions, clé=city
│
├── producers/                    ← Sous-partie D
│   └── event_producer.py         ← publication des 7 types d'événements
│
├── consumers/                    ← Sous-partie F
│   ├── consumer_a.py             ← agrégation par statut et par ville
│   └── consumer_b.py             ← agrégation par livreur
│
├── offsets/                      ← Sous-partie G
│   ├── offset_store.py           ← persistance thread-safe des offsets
│   ├── offsets_a.json            ← généré à l'exécution (Consumer A)
│   └── offsets_b.json            ← généré à l'exécution (Consumer B)
│
├── storage/                      ← Sous-partie H
│   └── partitioned_store.py      ← écriture JSONL par city=<ville>/
│
├── dashboard/                    ← Sous-partie I
│   └── dashboard.py              ← tableau de bord ASCII + export JSON
│
├── data/                         ← généré à l'exécution
│   ├── city=Fes/
│   │   └── events.jsonl
│   ├── city=Casablanca/
│   │   └── events.jsonl
│   ├── city=Rabat/
│   │   └── events.jsonl
│   ├── city=Marrakech/
│   │   └── events.jsonl
│   └── city=Tanger/
│       └── events.jsonl
│
└── logs/
    └── run.log                   ← généré à l'exécution
```

---

## Prérequis

- **Python 3.11+**
- **Aucune dépendance externe** — bibliothèque standard uniquement
- Extension **Python** (Microsoft) dans VS Code

---

## Architecture

```
Client
  │  (synchrone)
  ▼
OrderService ──validate──▶ Order
  │  (publie order_created)
  ▼
MiniBroker  ──partition_of(city)──▶  Partition 0..3
  │                                        │
  ├── Consumer A (partitions 0,2) ◀────────┤
  │     agrège : by_status, by_city        │
  └── Consumer B (partitions 1,3) ◀────────┘
        agrège : by_courier

OffsetStore ──────────────────────── offsets/offsets_a.json
                                      offsets/offsets_b.json

PartitionedStore ─────────────────── data/city=<ville>/events.jsonl

Dashboard ──────────────────────── affichage toutes les 8s
           └──────────────────────── rapport_final.json (à la fin)
```

---

## Clé de partition : `city`

| Avantage | Détail |
|---|---|
| Ordre garanti | Tous les événements d'une commande (même ville) dans la même partition |
| Isolation | Un consumer de Fès ne voit jamais les commandes de Casablanca |
| Lisibilité | Stockage `city=Fes/` directement exploitable |

**Risque de skew** : si une ville reçoit 80% des commandes, sa partition sera surchargée. Alternative : clé `order_id` (meilleure distribution, mais perte d'ordre par ville).

---

## Types d'événements

| Événement | Déclencheur | Consumers |
|---|---|---|
| `order_created` | OrderService (sync) | A + B |
| `order_confirmed` | Producteur | A |
| `order_prepared` | Producteur | A + B |
| `order_dispatched` | Producteur | A + B |
| `order_delivered` | Producteur | A + B |
| `order_cancelled` | Producteur | A |
| `delivery_failed` | Producteur | B |

---

## Garantie at-least-once

L'offset est commité toutes les `COMMIT_EVERY` (= 5) lectures. En cas de crash entre deux commits, les derniers messages seront relus au redémarrage — le traitement doit donc être **idempotent**.

---

## Scénarios de test recommandés

```bash
# Lancement standard
python run.py

# Tester la reprise après crash :
# 1. Lancer, attendre ~10s, Ctrl+C
# 2. Relancer — les consumers reprennent depuis les offsets sauvegardés

# Lire les données d'une ville directement
python -c "
import json
with open('data/city=Fes/events.jsonl') as f:
    for line in f: print(json.loads(line)['event_type'])
"
```

---

## Correspondance TP → Sous-parties

| Sous-partie | Fichier(s) |
|---|---|
| A — Analyse fonctionnelle | `README.md` (section Architecture) |
| B — Contrats de données | `contracts/order.py`, `contracts/event.py` |
| C — Service synchrone | `service/order_service.py` |
| D — Diffusion d'événements | `producers/event_producer.py` |
| E — Partitionnement | `broker/mini_broker.py` → `partition_of()` |
| F — Consumers | `consumers/consumer_a.py`, `consumer_b.py` |
| G — Offsets et reprise | `offsets/offset_store.py` |
| H — Stockage partitionné | `storage/partitioned_store.py` |
| I — Reporting | `dashboard/dashboard.py` |
| J — Analyse finale | À rédiger par l'étudiant |
