"""Moteur de calcul TRS selon la norme NF E60-182."""
import pandas as pd
import numpy as np
from typing import Optional
import re


def _convert_percentage_to_float(value):
    """Convertit un pourcentage en format texte (ex: '85,5%') en float (0.855)."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip().replace('%', '').replace(' ', '').replace(',', '.')
        try:
            return float(value) / 100 if value else 0.0
        except ValueError:
            return 0.0
    return 0.0


def _get_tps_requis_h(row: pd.Series) -> float:
    tps_requis = row.get("Tps Requis (h)")
    if pd.notna(tps_requis):
        return max(float(tps_requis), 0.0)
    tps_ouverture = row.get("Tps Ouverture (h)")
    arrets_non_imput = row.get("Arrets Non Imput.")
    if pd.notna(tps_ouverture) and pd.notna(arrets_non_imput):
        return max(float(tps_ouverture) - float(arrets_non_imput), 0.0)
    if pd.notna(tps_ouverture):
        return max(float(tps_ouverture), 0.0)
    tps_dispo = row.get("Tps Disponible (h)")
    if pd.notna(tps_dispo):
        return max(float(tps_dispo), 0.0)
    return 8.0


def calculate_taux_disponibilite(tps_fct_brut_h: float, tps_ouverture_h: float) -> float:
    """
    Calcule le taux de disponibilité.

    Formule: Do = Tps Fonctionnement Brut / Tps Ouverture

    Args:
        tps_fct_brut_h: Temps de fonctionnement brut en heures
        tps_ouverture_h: Temps d'ouverture en heures

    Returns:
        Taux de disponibilité (0.0 à 1.0+)
    """
    if tps_ouverture_h == 0 or pd.isna(tps_ouverture_h):
        return 0.0
    if pd.isna(tps_fct_brut_h):
        return 0.0
    return tps_fct_brut_h / tps_ouverture_h


def calculate_taux_performance(tps_net_h: float, tps_fct_brut_h: float) -> float:
    """
    Calcule le taux de performance.

    Formule: Tp = Tps Net / Tps Fonctionnement Brut
    Où Tps Net = Nb Cycles * Cycle Théorique

    Args:
        tps_net_h: Temps net en heures (Nb Cycles * Cycle Théo / 3600)
        tps_fct_brut_h: Temps de fonctionnement brut en heures

    Returns:
        Taux de performance (0.0 à 1.0+)
    """
    if tps_fct_brut_h == 0 or pd.isna(tps_fct_brut_h):
        return 0.0
    if pd.isna(tps_net_h):
        return 0.0
    return tps_net_h / tps_fct_brut_h


def calculate_taux_qualite(pieces_bonnes: int, pieces_fabriquees: int) -> float:
    """
    Calcule le taux de qualité.

    Formule: Tq = Pièces Bonnes / Pièces Fabriquées

    Args:
        pieces_bonnes: Nombre de pièces conformes
        pieces_fabriquees: Nombre total de pièces produites

    Returns:
        Taux de qualité (0.0 à 1.0+)
    """
    if pieces_fabriquees == 0 or pd.isna(pieces_fabriquees):
        return 0.0
    if pd.isna(pieces_bonnes):
        return 0.0
    return pieces_bonnes / pieces_fabriquees


def calculate_trs(taux_dispo: float, taux_perf: float, taux_qualite: float) -> float:
    """
    Calcule le TRS (Taux de Rendement Synthétique).

    Formule: TRS = Do * Tp * Tq

    Args:
        taux_dispo: Taux de disponibilité
        taux_perf: Taux de performance
        taux_qualite: Taux de qualité

    Returns:
        TRS (0.0 à 1.0+)
    """
    return taux_dispo * taux_perf * taux_qualite


def calculate_metrics_for_row(row: pd.Series) -> dict:
    """
    Calcule toutes les métriques TRS pour une ligne de données.

    Args:
        row: Ligne du DataFrame avec les colonnes ERP

    Returns:
        Dictionnaire avec les métriques calculées
    """
    # Extraction des valeurs avec gestion des NaN
    tps_requis_h = _get_tps_requis_h(row)
    tps_fct_brut_h = row.get("Tps Fct Brut (h)", 0) or 0
    nb_cycles = row.get("Nb Cycles", 0) or 0
    cycle_theo_s = row.get("Cycle Théo", 0) or 0
    pieces_fab = row.get("Qté Pieces Fab.", 0) or 0
    pieces_bonnes = row.get("Qté Pieces Bonnes", 0) or 0

    # Calcul du temps net (en heures)
    tps_net_h = (nb_cycles * cycle_theo_s) / 3600 if cycle_theo_s else 0

    # Calcul des taux réels
    taux_dispo_reel = calculate_taux_disponibilite(tps_fct_brut_h, tps_requis_h)
    taux_perf_reel = calculate_taux_performance(tps_net_h, tps_fct_brut_h)
    taux_qualite_reel = calculate_taux_qualite(pieces_bonnes, pieces_fab)
    trs_reel = calculate_trs(taux_dispo_reel, taux_perf_reel, taux_qualite_reel)

    return {
        "tps_net_h": tps_net_h,
        "taux_dispo_reel": taux_dispo_reel,
        "taux_perf_reel": taux_perf_reel,
        "taux_qualite_reel": taux_qualite_reel,
        "trs_reel": trs_reel,
    }


def calculate_trs_réel_nf60182(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule le TRS Calculé selon la norme NF E60-182."""
    df = df.copy()

    # ===== CALCUL LIGNE PAR LIGNE =====
    for idx, row in df.iterrows():
        # Extraction des valeurs
        tps_requis_h = _get_tps_requis_h(row)
        tps_fct_brut_h = row.get("Tps Fct Brut (h)", 0.0) or 0.0
        nb_cycles = row.get("Nb Cycles", 0) or 0
        cycle_theo = row.get("Cycle Théo", 0) or 0
        pieces_bonnes = row.get("Qté Pieces Bonnes", 0) or 0
        pieces_fab = row.get("Qté Pieces Fab.", 1) or 1
        trs_erp = row.get("T.R.S.", 0.0) or 0.0

        # ===== Disponibilité (Do) =====
        if tps_requis_h > 0:
            do_réel = tps_fct_brut_h / tps_requis_h
        else:
            do_réel = 0.0

        # ===== Performance (Tp) =====
        if tps_fct_brut_h > 0 and cycle_theo > 0:
            tps_net_h = (nb_cycles * cycle_theo) / 3600
            tp_réel = tps_net_h / tps_fct_brut_h
        else:
            tp_réel = 0.0

        # ===== Qualité (Tq) =====
        pieces_bonnes_abs = abs(pieces_bonnes)
        if pieces_fab > 0:
            tq_réel = pieces_bonnes_abs / pieces_fab
        else:
            tq_réel = 0.0

        # ===== TRS Audit =====
        trs_réel = do_réel * tp_réel * tq_réel

        # Nettoyer les Inf et NaN
        if np.isnan(trs_réel) or np.isinf(trs_réel):
            trs_réel = 0.0

        # Limiter à 1.5 pour éviter les valeurs absurdes
        trs_réel = max(0.0, min(trs_réel, 1.5))

        # Stocker les valeurs calculées
        df.at[idx, "Tps Requis (h)"] = tps_requis_h
        df.at[idx, "Do_Calc"] = do_réel
        df.at[idx, "Tp_Calc"] = tp_réel
        df.at[idx, "Tq_Calc"] = tq_réel
        df.at[idx, "TRS_Calc"] = trs_réel
        df.at[idx, "Do_Réel"] = do_réel
        df.at[idx, "Tp_Réel"] = tp_réel
        df.at[idx, "Tq_Réel"] = tq_réel
        df.at[idx, "TRS_Réel"] = trs_réel
        df.at[idx, "TRS_Écart"] = trs_erp - trs_réel
        df.at[idx, "TRS_ERP_Surestime"] = (trs_erp - trs_réel) > 0.001

    return df


def detect_anomalies(row: pd.Series) -> list:
    """Détecte les anomalies dans les DONNÉES ERP BRUTES."""
    anomalies = []

    # T.R.S. ERP hors limites
    trs_erp = row.get("T.R.S.", 0)
    if pd.notna(trs_erp) and (trs_erp > 1.0 or trs_erp < 0):
        anomalies.append("trs_erp_hors_limites")

    # Taux Performance ERP hors limites
    taux_perf = row.get("Taux Performance", 0)
    if pd.notna(taux_perf) and (taux_perf > 1.0 or taux_perf < 0):
        anomalies.append("perf_erp_hors_limites")
        if taux_perf > 1.0:
            anomalies.append("performance_superieure_100")

    # Taux Qualité ERP hors limites
    taux_qualite = row.get("Taux Qualité", 0)
    if pd.notna(taux_qualite) and (taux_qualite > 1.0 or taux_qualite < 0):
        anomalies.append("qualite_erp_hors_limites")

    # Pièces négatives
    pieces_bonnes = row.get("Qté Pieces Bonnes", 0)
    if pd.notna(pieces_bonnes) and pieces_bonnes < 0:
        anomalies.append("pieces_negatives")

    # Rebuts > Production
    rebuts = row.get("Total Rebuts", 0) or 0
    pieces_fab = row.get("Qté Pieces Fab.", 0) or 0
    if rebuts > pieces_fab and pieces_fab > 0:
        anomalies.append("rebuts_superieurs_production")

    return anomalies


def calculate_trs_audit_final(df: pd.DataFrame) -> dict:
    """Calcule l'écart entre TRS ERP et TRS Réel."""
    if df.empty:
        return {
            'trs_erp': 0.0,
            'trs_réel': 0.0,
            'écart_points': 0.0,
            'écart_pct': 0.0,
            'lignes_production': 0,
            'lignes_totales': 0,
            'lignes_zéro': 0,
            'do_réel': 0.0,
            'tp_réel': 0.0,
            'tq_réel': 0.0,
        }

    # ===== TRS ERP (exclut zéros) =====
    if 'Tps Fct Brut (h)' in df.columns and 'T.R.S.' in df.columns:
        df_prod = df[
            (df['Tps Fct Brut (h)'].fillna(0) > 0) |
            (df['T.R.S.'].fillna(0) > 0)
        ].copy()
    else:
        df_prod = pd.DataFrame()

    if len(df_prod) > 0 and 'T.R.S.' in df_prod.columns:
        trs_erp = df_prod['T.R.S.'].mean()
    else:
        trs_erp = 0.0

    # ===== TRS RÉEL (inclut tout) =====
    total_tps_dispo = df['Tps Disponible (h)'].fillna(0).sum() if 'Tps Disponible (h)' in df.columns else 0.0
    total_tps_utile = df['Tps Utile (h)'].fillna(0).sum() if 'Tps Utile (h)' in df.columns else 0.0

    if total_tps_dispo > 0:
        trs_réel = total_tps_utile / total_tps_dispo
    else:
        trs_réel = 0.0

    # Composantes du TRS Réel (global)
    total_tps_fct_brut = df['Tps Fct Brut (h)'].fillna(0).sum() if 'Tps Fct Brut (h)' in df.columns else 0.0
    total_tps_net = df['Tps Fct Net (h)'].fillna(0).sum() if 'Tps Fct Net (h)' in df.columns else 0.0

    do_réel = total_tps_fct_brut / total_tps_dispo if total_tps_dispo > 0 else 0.0
    tp_réel = total_tps_net / total_tps_fct_brut if total_tps_fct_brut > 0 else 0.0
    tq_réel = total_tps_utile / total_tps_net if total_tps_net > 0 else 0.0

    # ===== COMPOSANTES ERP (globales) =====
    if len(df_prod) > 0:
        total_tps_dispo_prod = df_prod['Tps Disponible (h)'].fillna(0).sum() if 'Tps Disponible (h)' in df_prod.columns else 0.0
        total_tps_fct_brut_prod = df_prod['Tps Fct Brut (h)'].fillna(0).sum() if 'Tps Fct Brut (h)' in df_prod.columns else 0.0
        total_tps_net_prod = df_prod['Tps Fct Net (h)'].fillna(0).sum() if 'Tps Fct Net (h)' in df_prod.columns else 0.0
        total_tps_utile_prod = df_prod['Tps Utile (h)'].fillna(0).sum() if 'Tps Utile (h)' in df_prod.columns else 0.0

        do_erp = total_tps_fct_brut_prod / total_tps_dispo_prod if total_tps_dispo_prod > 0 else 0.0
        tp_erp = total_tps_net_prod / total_tps_fct_brut_prod if total_tps_fct_brut_prod > 0 else 0.0
        tq_erp = total_tps_utile_prod / total_tps_net_prod if total_tps_net_prod > 0 else 0.0
    else:
        do_erp = 0.0
        tp_erp = 0.0
        tq_erp = 0.0

    # ===== ÉCART =====
    écart = trs_erp - trs_réel
    écart_pct = (écart / trs_réel * 100) if trs_réel > 0 else 0.0

    # ===== STATISTIQUES =====
    lignes_totales = len(df)
    lignes_production = len(df_prod)
    lignes_zéro = lignes_totales - lignes_production

    return {
        'trs_erp': float(trs_erp),
        'trs_réel': float(trs_réel),
        'écart_points': float(écart),
        'écart_pct': float(écart_pct),
        'lignes_production': int(lignes_production),
        'lignes_totales': int(lignes_totales),
        'lignes_zéro': int(lignes_zéro),
        'do_réel': float(do_réel),
        'tp_réel': float(tp_réel),
        'tq_réel': float(tq_réel),
        'do_erp': float(do_erp),
        'tp_erp': float(tp_erp),
        'tq_erp': float(tq_erp),
    }


def calculate_all_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les métriques TRS pour tout le DataFrame."""
    df = df.copy()

    # Convertir les colonnes de pourcentage texte en nombres
    percentage_columns = ['Taux Performance', 'Taux Qualité', 'T.R.S.', 'T.R.G.']
    for col in percentage_columns:
        if col in df.columns:
            df[col] = df[col].apply(_convert_percentage_to_float)

    # Calcul des métriques pour chaque ligne
    metrics_list = df.apply(calculate_metrics_for_row, axis=1)
    metrics_df = pd.DataFrame(metrics_list.tolist())

    # Ajouter les colonnes calculées
    for col in metrics_df.columns:
        df[col] = metrics_df[col].values

    # Calcul du TRS Audit selon NF E60-182
    df = calculate_trs_réel_nf60182(df)

    # Détection des anomalies
    df["anomalies"] = df.apply(detect_anomalies, axis=1)
    df["is_anomaly"] = df["anomalies"].apply(lambda x: len(x) > 0)

    # Lignes à TRS = 0
    df["is_zero_trs"] = (df.get("T.R.S.", 0) == 0) | (df.get("TRS_Calc", 0) == 0)

    return df
