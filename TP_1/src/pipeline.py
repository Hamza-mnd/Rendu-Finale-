"""
Pipeline ETL – Station Météo & Irrigation
Séance 1 – Data Engineering avec Python

Auteur : [Votre Nom]
Date   : 2025
"""

import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG = {
    "input_path":       "data/raw/meteo_brut.csv",
    "output_clean":     "outputs/meteo_clean.csv",
    "output_features":  "outputs/meteo_features.csv",
    "output_report":    "outputs/quality_report.txt",
    "log_file":         "logs/pipeline.log",
    "date_format":      "%Y-%m-%d",
    "temp_min":         -40,
    "temp_max":         60,
    "humidity_min":     0,
    "humidity_max":     100,
    "irrigation_map":   {"ON": "ON", "OFF": "OFF", "OUI": "ON", "NON": "OFF"},
}

# ============================================================
# LOGGING
# ============================================================
def setup_logging(log_file):
    """Configure le logging : console (INFO) + fichier (DEBUG)."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_h = logging.StreamHandler()
    console_h.setLevel(logging.INFO)
    console_h.setFormatter(fmt)

    file_h = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console_h)
    root.addHandler(file_h)

logger = logging.getLogger("pipeline")

# ============================================================
# EXTRACT
# ============================================================
def extract(filepath):
    """Lit le fichier CSV brut. Échoue proprement si le fichier n'existe pas.

    Args:
        filepath: Chemin vers le fichier CSV source.

    Returns:
        DataFrame brut non modifié.

    Raises:
        SystemExit: si le fichier est introuvable.
    """
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        logger.error("Fichier introuvable : %s", filepath)
        raise SystemExit(1)

    logger.info("EXTRACT : %d lignes × %d colonnes chargées depuis '%s'",
                len(df), len(df.columns), filepath)
    logger.debug("Colonnes : %s", list(df.columns))
    return df

# ============================================================
# TRANSFORM
# ============================================================
def detect_outliers_iqr(series, factor=1.5):
    """Détecte les outliers par la méthode IQR.

    Args:
        series: Series pandas numérique.
        factor: Multiplicateur IQR (défaut 1.5).

    Returns:
        Series booléenne (True = outlier potentiel).
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - factor * iqr
    upper = q3 + factor * iqr
    return (series < lower) | (series > upper)


def transform(df, config):
    """Nettoie et transforme le DataFrame brut.

    Étapes :
        1. Harmonisation des colonnes textuelles (station, irrigation)
        2. Conversion de types (numériques, dates)
        3. Suppression des doublons
        4. Traitement des valeurs invalides (hors domaine)
        5. Détection d'outliers (wind_kmh par IQR)
        6. Suppression des lignes sans date
        7. Imputation des valeurs manquantes

    Args:
        df: DataFrame brut (non modifié en place).
        config: Dictionnaire de configuration.

    Returns:
        DataFrame nettoyé (copie indépendante).
    """
    df = df.copy()
    n_initial = len(df)
    logger.info("TRANSFORM : début — %d lignes", n_initial)

    # --- 1. Harmonisation station ---
    # Normalise en majuscules pour homogénéiser "st-01" → "ST-01"
    df['station'] = df['station'].str.strip().str.upper()
    logger.debug("  station : harmonisée en majuscules")

    # --- 2. Harmonisation irrigation ---
    # strip + upper pour gérer "off", "OFF", "OUI", "NON", etc.
    df['irrigation'] = (
        df['irrigation']
        .str.strip()
        .str.upper()
        .map(config['irrigation_map'])
    )
    n_unmapped = df['irrigation'].isna().sum()
    if n_unmapped > 0:
        logger.warning("  irrigation : %d valeur(s) non reconnue(s) → NaN", n_unmapped)
    else:
        logger.debug("  irrigation : toutes les valeurs mappées (ON/OFF)")

    # --- 3. Conversion des colonnes numériques ---
    num_cols = ['temperature', 'humidity', 'rain_mm', 'wind_kmh']
    for col in num_cols:
        before_na = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors='coerce')
        coerced = df[col].isna().sum() - before_na
        if coerced > 0:
            logger.warning("  %s : %d valeur(s) non numérique(s) → NaN", col, coerced)

    # --- 4. Parsing des dates ---
    before_nat = df['date'].isna().sum()
    df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')
    nat_created = df['date'].isna().sum() - before_nat
    if nat_created > 0:
        logger.warning("  date : %d valeur(s) invalide(s) ou impossible(s) → NaT "
                       "(ex. format dd/mm/yyyy, 2025-02-30)", nat_created)

    # --- 5. Suppression des doublons ---
    n_dups = df.duplicated().sum()
    if n_dups > 0:
        df = df.drop_duplicates()
        logger.warning("  %d doublon(s) exact(s) supprimé(s)", n_dups)
    else:
        logger.debug("  Aucun doublon détecté")

    # --- 6. Valeurs hors domaine ---
    # temperature hors [-40, 60] → NaN (erreur capteur, ex. 999 °C impossible)
    mask_temp = (
        (df['temperature'] < config['temp_min']) |
        (df['temperature'] > config['temp_max'])
    )
    n_temp_invalid = mask_temp.sum()
    if n_temp_invalid > 0:
        df.loc[mask_temp, 'temperature'] = np.nan
        logger.warning("  temperature : %d valeur(s) hors [%d, %d] → NaN",
                       n_temp_invalid, config['temp_min'], config['temp_max'])

    # humidity hors [0, 100] → NaN (humidité négative physiquement impossible)
    mask_hum = (
        (df['humidity'] < config['humidity_min']) |
        (df['humidity'] > config['humidity_max'])
    )
    n_hum_invalid = mask_hum.sum()
    if n_hum_invalid > 0:
        df.loc[mask_hum, 'humidity'] = np.nan
        logger.warning("  humidity : %d valeur(s) hors [%d, %d] → NaN",
                       n_hum_invalid, config['humidity_min'], config['humidity_max'])

    # --- 7. Outliers wind_kmh (IQR) ---
    # Décision : on conserve les valeurs même outliers (150 km/h = vent de tempête,
    # physiquement possible en France métropolitaine). On logue uniquement pour
    # traçabilité. Si le contexte métier imposait des plafonds, on supprimerail ici.
    wind_outliers = detect_outliers_iqr(df['wind_kmh'].dropna())
    n_wind_out = wind_outliers.sum()
    if n_wind_out > 0:
        logger.warning("  wind_kmh : %d outlier(s) IQR détecté(s) — CONSERVÉ(S) "
                       "(vent de tempête plausible, décision métier)", n_wind_out)

    # --- 8. Suppression des lignes sans date ---
    # Sans date, la ligne est inutilisable pour l'analyse temporelle.
    n_before_dropdate = len(df)
    df = df.dropna(subset=['date'])
    n_dropped_date = n_before_dropdate - len(df)
    if n_dropped_date > 0:
        logger.warning("  date : %d ligne(s) sans date supprimée(s)", n_dropped_date)

    # --- 9. Imputation des valeurs manquantes ---

    # temperature → médiane par station (préserve les variations locales)
    n_temp_nan = df['temperature'].isna().sum()
    if n_temp_nan > 0:
        df['temperature'] = df['temperature'].fillna(
            df.groupby('station')['temperature'].transform('median')
        )
        logger.info("  temperature : %d NaN imputé(s) par médiane par station", n_temp_nan)

    # humidity → médiane globale (pas assez de lignes par station pour être précis)
    n_hum_nan = df['humidity'].isna().sum()
    if n_hum_nan > 0:
        df['humidity'] = df['humidity'].fillna(df['humidity'].median())
        logger.info("  humidity : %d NaN imputé(s) par médiane globale (%.1f)",
                    n_hum_nan, df['humidity'].median())

    # rain_mm → 0.0 (hypothèse : absence de mesure = pas de pluie)
    n_rain_nan = df['rain_mm'].isna().sum()
    if n_rain_nan > 0:
        df['rain_mm'] = df['rain_mm'].fillna(0.0)
        logger.info("  rain_mm : %d NaN imputé(s) par 0.0 (pas de mesure = pas de pluie)",
                    n_rain_nan)

    logger.info("TRANSFORM : fin — %d lignes conservées (sur %d)", len(df), n_initial)
    return df

# ============================================================
# QUALITY REPORT
# ============================================================
def quality_report(df_raw, df_clean, filepath):
    """Génère un rapport de qualité et l'exporte en fichier TXT.

    Le rapport contient : timestamp, lignes entrée/sortie, doublons,
    taux de missing par colonne, outliers détectés, statistiques descriptives.

    Args:
        df_raw:   DataFrame brut (avant nettoyage).
        df_clean: DataFrame nettoyé.
        filepath: Chemin du fichier TXT de sortie.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    lines = []

    SEP = "=" * 60
    SEP2 = "-" * 60

    lines.append(SEP)
    lines.append("RAPPORT DE QUALITÉ – Pipeline Météo & Irrigation")
    lines.append(f"Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(SEP)
    lines.append("")

    # --- Lignes en entrée / sortie ---
    lines.append("1. VOLUMÉTRIE")
    lines.append(SEP2)
    lines.append(f"  Lignes en entrée   : {len(df_raw)}")
    lines.append(f"  Lignes en sortie   : {len(df_clean)}")
    lines.append(f"  Lignes supprimées  : {len(df_raw) - len(df_clean)}")
    lines.append("")

    # --- Doublons ---
    n_dups = df_raw.duplicated().sum()
    lines.append("2. DOUBLONS")
    lines.append(SEP2)
    lines.append(f"  Doublons détectés  : {n_dups}")
    lines.append("")

    # --- Taux de missing par colonne (sur le brut) ---
    lines.append("3. VALEURS MANQUANTES (dataset brut)")
    lines.append(SEP2)
    for col in df_raw.columns:
        n_miss = df_raw[col].isna().sum()
        pct = 100 * n_miss / len(df_raw)
        lines.append(f"  {col:<15} : {n_miss:>3} NaN  ({pct:5.1f} %)")
    lines.append("")

    # --- Outliers détectés (sur numériques du brut, après coercion) ---
    lines.append("4. OUTLIERS DÉTECTÉS (IQR, dataset brut)")
    lines.append(SEP2)
    num_cols = ['temperature', 'humidity', 'rain_mm', 'wind_kmh']
    df_raw_num = df_raw.copy()
    for col in num_cols:
        df_raw_num[col] = pd.to_numeric(df_raw_num[col], errors='coerce')
        series = df_raw_num[col].dropna()
        n_out = detect_outliers_iqr(series).sum()
        lines.append(f"  {col:<15} : {n_out:>2} outlier(s) IQR")
    lines.append("")

    # --- Statistiques descriptives (dataset clean) ---
    lines.append("5. STATISTIQUES DESCRIPTIVES (dataset nettoyé)")
    lines.append(SEP2)
    stat_cols = ['temperature', 'humidity', 'rain_mm', 'wind_kmh']
    header = f"  {'Colonne':<15} {'Min':>8} {'Max':>8} {'Moyenne':>10} {'Médiane':>10}"
    lines.append(header)
    lines.append("  " + "-" * 55)
    for col in stat_cols:
        s = df_clean[col]
        lines.append(
            f"  {col:<15} {s.min():>8.2f} {s.max():>8.2f} "
            f"{s.mean():>10.2f} {s.median():>10.2f}"
        )
    lines.append("")

    lines.append(SEP)
    lines.append("FIN DU RAPPORT")
    lines.append(SEP)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Rapport qualité exporté : %s", filepath)

# ============================================================
# BUILD FEATURES
# ============================================================
def build_features(df):
    """Crée des features dérivées, toutes vectorisées (sans apply ni boucle for).

    Features créées :
        - jour_semaine    : jour de la semaine (0=lundi … 6=dimanche)
        - temp_classe     : catégorie température (froid / tempéré / chaud)
        - irrigation_bin  : 1 si ON, 0 si OFF
        - heat_index      : température + 0.5 × humidité (indicateur de ressenti)
        - besoin_arrosage : 1 si pas de pluie ET température > 25°C, sinon 0

    Args:
        df: DataFrame nettoyé.

    Returns:
        DataFrame enrichi (copie).
    """
    df = df.copy()

    # Feature 1 : jour de la semaine (extraction temporelle)
    df['jour_semaine'] = df['date'].dt.dayofweek

    # Feature 2 : classe de température (discrétisation vectorisée)
    df['temp_classe'] = pd.cut(
        df['temperature'],
        bins=[-40, 15, 25, 60],
        labels=['froid', 'tempéré', 'chaud'],
        right=True
    )

    # Feature 3 : encodage binaire de l'irrigation
    df['irrigation_bin'] = (df['irrigation'] == 'ON').astype(int)

    # Feature 4 : heat index simplifié (combinaison de colonnes)
    df['heat_index'] = df['temperature'] + 0.5 * df['humidity']

    # Feature 5 : besoin d'arrosage (règle métier vectorisée)
    df['besoin_arrosage'] = np.where(
        (df['rain_mm'] == 0) & (df['temperature'] > 25),
        1, 0
    )

    features_added = ['jour_semaine', 'temp_classe', 'irrigation_bin',
                       'heat_index', 'besoin_arrosage']
    logger.info("BUILD FEATURES : %d features créées → %s",
                len(features_added), features_added)
    return df

# ============================================================
# LOAD
# ============================================================
def load(df_clean, df_features, config):
    """Exporte les DataFrames nettoyé et enrichi en CSV (idempotent : écrase).

    Args:
        df_clean:    DataFrame nettoyé (sans les features).
        df_features: DataFrame nettoyé + features.
        config:      Dictionnaire de configuration.
    """
    os.makedirs("outputs", exist_ok=True)

    df_clean.to_csv(config['output_clean'], index=False)
    logger.info("LOAD : meteo_clean.csv exporté (%d lignes) → %s",
                len(df_clean), config['output_clean'])

    df_features.to_csv(config['output_features'], index=False)
    logger.info("LOAD : meteo_features.csv exporté (%d lignes, %d colonnes) → %s",
                len(df_features), len(df_features.columns), config['output_features'])

# ============================================================
# MAIN
# ============================================================
def main():
    """Point d'entrée du pipeline ETL."""
    setup_logging(CONFIG["log_file"])
    logger.info("=" * 50)
    logger.info("DÉMARRAGE DU PIPELINE")
    logger.info("=" * 50)

    start = datetime.now()

    # 1. Extract
    df_raw = extract(CONFIG["input_path"])

    # 2. Transform
    df_clean = transform(df_raw, CONFIG)

    # 3. Quality report
    quality_report(df_raw, df_clean, CONFIG["output_report"])

    # 4. Features
    df_features = build_features(df_clean)

    # 5. Load
    load(df_clean, df_features, CONFIG)

    # --- Assertions de validation post-pipeline ---
    assert len(df_clean) > 0, "Le DataFrame clean est vide !"
    assert df_clean['date'].isna().sum() == 0, "Il reste des dates NaT !"
    assert df_clean['temperature'].isna().sum() == 0, "Il reste des NaN dans temperature !"
    assert set(df_clean['irrigation'].unique()) <= {'ON', 'OFF'}, \
        f"Valeurs inattendues dans irrigation : {df_clean['irrigation'].unique()}"
    assert (df_clean['humidity'] >= 0).all(), "humidity < 0 détectée"
    assert (df_clean['humidity'] <= 100).all(), "humidity > 100 détectée"
    assert df_clean.duplicated().sum() == 0, "Doublons dans le dataset clean !"
    expected_feats = {'jour_semaine', 'temp_classe', 'irrigation_bin'}
    assert expected_feats.issubset(df_features.columns), \
        f"Features manquantes : {expected_feats - set(df_features.columns)}"
    assert len(df_clean) == len(df_features), "Incohérence de taille clean vs features"
    logger.info("✅ Toutes les assertions passent.")

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("=" * 50)
    logger.info("PIPELINE TERMINÉ en %.2f secondes", elapsed)
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
