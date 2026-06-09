# TP1 – Pipeline ETL Météo & Irrigation

## Objectif

Construire un pipeline ETL complet en Python sur un jeu de données de stations météo.  
Le pipeline couvre : extraction, nettoyage, rapport qualité, feature engineering et export.

---

## Prérequis

- Python 3.10+
- pip

---

## Installation

```bash
# 1. Cloner ou télécharger le dossier meteo_pipeline
cd meteo_pipeline

# 2. Créer et activer l'environnement virtuel
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt
```

---

## Lancement

```bash
# Depuis la racine de meteo_pipeline/
python src/pipeline.py
```

---

## Structure du projet

```
meteo_pipeline/
├── requirements.txt
├── src/
│   └── pipeline.py          # Code source du pipeline ETL
├── data/
│   └── raw/
│       └── meteo_brut.csv   # Données brutes (16 lignes, 8 colonnes)
├── outputs/
│   ├── meteo_clean.csv      # Données nettoyées (13 lignes)
│   ├── meteo_features.csv   # Données + features dérivées
│   └── quality_report.txt   # Rapport de qualité généré automatiquement
└── logs/
    └── pipeline.log         # Journal d'exécution (généré automatiquement)
```

---

## Étapes du pipeline

| Étape | Fonction | Description |
|---|---|---|
| Extract | `extract()` | Lecture du CSV brut avec gestion d'erreur |
| Transform | `transform()` | Nettoyage complet (doublons, types, outliers, imputation) |
| Quality report | `quality_report()` | Génération du rapport TXT |
| Features | `build_features()` | Création de 5 features vectorisées |
| Load | `load()` | Export des CSV propres |

---

## Problèmes traités dans les données

| Ligne | Problème | Décision |
|---|---|---|
| 4 | `temperature = "vingt"` (texte) | Coercion → NaN → imputation médiane ST-01 |
| 5 | Date format `dd/mm/yyyy` | Parsing automatique → corrigé |
| 6 | Doublon exact de la ligne 2 | Suppression |
| 7 | `humidity` manquante | Imputation par médiane globale |
| 8 | `temperature = 999` (hors [-40, 60]) | → NaN → imputation médiane ST-01 |
| 8 | `irrigation = "OUI"` | Normalisé → `ON` |
| 9 | Date impossible `2025-02-30` | → NaT → ligne supprimée |
| 10 | `humidity = -5` (invalide) | → NaN → imputation médiane globale |
| 11 | `wind_kmh = 150` (outlier IQR) | Conservé (tempête plausible) |
| 12 | `rain_mm` manquant | Imputation par `0.0` |
| 15 | `date` manquante | Ligne supprimée |
| 3, 13 | `irrigation = "off"` | Normalisé → `OFF` |

---

## Features créées

| Feature | Type | Logique |
|---|---|---|
| `jour_semaine` | Extraction temporelle | `date.dt.dayofweek` (0=lundi) |
| `temp_classe` | Discrétisation | froid < 15°C / tempéré 15–25°C / chaud > 25°C |
| `irrigation_bin` | Encodage binaire | 1 si ON, 0 si OFF |
| `heat_index` | Combinaison | `temperature + 0.5 × humidity` |
| `besoin_arrosage` | Règle métier | 1 si `rain_mm == 0` et `temperature > 25` |

---

## Résultats

- Lignes en entrée : **16**
- Lignes en sortie : **13**
- Features ajoutées : **5**
- Toutes les assertions de validation passent ✅
