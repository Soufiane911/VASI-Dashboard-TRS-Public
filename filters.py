"""Module de filtrage des données avec mise à jour temps réel."""
import pandas as pd
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class FilterConfig:
    """Configuration des filtres."""

    # Filtres rapides (checkboxes)
    include_sous_charge: bool = True
    include_zero_trs: bool = True
    include_anomalies: bool = True

    # Filtres avancés
    min_trs: float = 0.0
    max_trs: float = 2.0
    min_performance: float = 0.0
    max_performance: float = 2.5
    machines: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convertit en dictionnaire."""
        return {
            "include_sous_charge": self.include_sous_charge,
            "include_zero_trs": self.include_zero_trs,
            "include_anomalies": self.include_anomalies,
            "min_trs": self.min_trs,
            "max_trs": self.max_trs,
            "min_performance": self.min_performance,
            "max_performance": self.max_performance,
            "machines": self.machines,
        }


def _get_tps_requis_series(df: pd.DataFrame) -> pd.Series:
    if "Tps Requis (h)" in df.columns:
        return df["Tps Requis (h)"]
    if "Tps Ouverture (h)" in df.columns and "Arrets Non Imput." in df.columns:
        return (df["Tps Ouverture (h)"] - df["Arrets Non Imput."]).clip(lower=0)
    if "Tps Ouverture (h)" in df.columns:
        return df["Tps Ouverture (h)"].clip(lower=0)
    if "Tps Disponible (h)" in df.columns:
        return df["Tps Disponible (h)"].clip(lower=0)
    return pd.Series([0.0] * len(df), index=df.index)


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Applique les filtres au DataFrame."""
    if df.empty:
        return df

    result = df.copy()

    # Filtre Sous-charge
    if not filters.get("include_sous_charge", True):
        if "Type OF" in result.columns:
            result = result[result["Type OF"] != "Sous-charge"]

    # Filtre TRS = 0
    if not filters.get("include_zero_trs", True):
        if "is_zero_trs" in result.columns:
            result = result[~result["is_zero_trs"]]

    # Filtre anomalies
    if not filters.get("include_anomalies", True):
        if "is_anomaly" in result.columns:
            result = result[~result["is_anomaly"]]

    # Filtres avancés: plage TRS
    min_trs = filters.get("min_trs", 0.0)
    max_trs = filters.get("max_trs", 2.0)
    if "TRS_Calc" in result.columns:
        result = result[(result["TRS_Calc"] >= min_trs) & (result["TRS_Calc"] <= max_trs)]

    # Filtres avancés: plage Performance
    min_perf = filters.get("min_performance", 0.0)
    max_perf = filters.get("max_performance", 2.5)
    if "Tp_Calc" in result.columns:
        result = result[(result["Tp_Calc"] >= min_perf) & (result["Tp_Calc"] <= max_perf)]

    # Filtres avancés: machines spécifiques
    machines = filters.get("machines", [])

    def _match_val(val, selected):
        if pd.isna(val) or selected is None: return False
        try:
            v_str = str(int(float(val))) if float(val).is_integer() else str(val)
            s_str = str(int(float(selected))) if float(selected).is_integer() else str(selected)
            return v_str == s_str
        except:
            return str(val) == str(selected)

    if machines and "Réf. Machine" in result.columns:
        result = result[result["Réf. Machine"].apply(lambda x: any(_match_val(x, m) for m in machines))]

    # ===== NOUVEAUX FILTRES DROPDOWN =====
    # Filtre Mois
    mois_selected = filters.get("mois_selected")
    if mois_selected and mois_selected != "Tous" and "Mois" in result.columns:
        result = result[result["Mois"] == mois_selected]

    # Filtre Presse
    presse_selected = filters.get("presse_selected")
    if presse_selected and presse_selected != "Toutes" and "Réf. Machine" in result.columns:
        result = result[result["Réf. Machine"].apply(lambda x: _match_val(x, presse_selected))]

    # Filtre Outillage
    outillage_selected = filters.get("outillage_selected")
    if outillage_selected and outillage_selected != "Tous" and "Réf. outil" in result.columns:
        result = result[result["Réf. outil"].apply(lambda x: _match_val(x, outillage_selected))]

    # Filtre Pièce
    piece_selected = filters.get("piece_selected")
    if piece_selected and piece_selected != "Toutes" and "Réf. produit" in result.columns:
        result = result[result["Réf. produit"].apply(lambda x: _match_val(x, piece_selected))]

    return result


def calculate_filter_stats(df: pd.DataFrame, filters: dict) -> dict:
    """Calcule les statistiques après filtrage."""
    total_rows = len(df)
    filtered_df = apply_filters(df, filters)
    filtered_rows = len(filtered_df)

    # Compteurs spécifiques
    zero_trs_count = df["is_zero_trs"].sum() if "is_zero_trs" in df.columns else 0
    anomaly_count = df["is_anomaly"].sum() if "is_anomaly" in df.columns else 0
    ok_count = total_rows - anomaly_count

    return {
        "total_rows": total_rows,
        "filtered_rows": filtered_rows,
        "excluded_rows": total_rows - filtered_rows,
        "zero_trs_count": int(zero_trs_count),
        "anomaly_count": int(anomaly_count),
        "ok_count": int(ok_count),
        "ok_percentage": (ok_count / total_rows * 100) if total_rows > 0 else 0,
        "anomaly_percentage": (anomaly_count / total_rows * 100) if total_rows > 0 else 0,
    }


def calculate_monthly_trs_table(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule TRS Réel et TRS ERP par mois."""
    if df.empty or "Mois" not in df.columns:
        return pd.DataFrame(columns=["Mois", "TRS_Réel", "TRS_ERP", "Écart", "Écart_%"])

    results = []

    for mois, group in df.groupby("Mois"):
        # ===== TRS ERP (exclut zéros) =====
        if 'Tps Fct Brut (h)' in group.columns and 'T.R.S.' in group.columns:
            group_prod = group[
                (group['Tps Fct Brut (h)'].fillna(0) > 0) |
                (group['T.R.S.'].fillna(0) > 0)
            ]
            trs_erp = group_prod['T.R.S.'].mean() if len(group_prod) > 0 else 0.0
        else:
            trs_erp = group["T.R.S."].mean() if "T.R.S." in group.columns else 0.0

        # ===== TRS Réel (NF E60-182) =====
        total_tps_dispo = group['Tps Disponible (h)'].fillna(0).sum() if 'Tps Disponible (h)' in group.columns else 0.0
        total_tps_utile = group['Tps Utile (h)'].fillna(0).sum() if 'Tps Utile (h)' in group.columns else 0.0

        if total_tps_dispo > 0:
            trs_reel = total_tps_utile / total_tps_dispo
        else:
            trs_reel = 0.0

        # Écarts
        ecart = trs_erp - trs_reel
        ecart_pct = (ecart / trs_reel * 100) if trs_reel > 0 else 0.0

        results.append({
            "Mois": mois,
            "TRS_Réel": trs_reel,
            "TRS_ERP": trs_erp,
            "Écart": ecart,
            "Écart_%": ecart_pct,
        })

    return pd.DataFrame(results).sort_values("Mois")


def calculate_aggregated_kpis(df: pd.DataFrame) -> dict:
    """Calcule les KPIs agrégés."""
    if df.empty:
        return {
            "trs_erp": 0.0,
            "trs_calc": 0.0,
            "trs_réel": 0.0,
            "delta_trs": 0.0,
            "taux_dispo_erp": 0.0,
            "taux_dispo_calc": 0.0,
            "taux_dispo_réel": 0.0,
            "taux_perf_erp": 0.0,
            "taux_perf_calc": 0.0,
            "taux_perf_réel": 0.0,
            "taux_qualite_erp": 0.0,
            "taux_qualite_calc": 0.0,
            "taux_qualite_réel": 0.0,
            "écart_points": 0.0,
            "écart_pourcentage": 0.0,
            "lignes_production": 0,
            "lignes_totales": 0,
            "lignes_zéro": 0,
        }

    # Utiliser la fonction d'audit finale
    try:
        from calculator import calculate_trs_audit_final
    except ImportError:
        from .calculator import calculate_trs_audit_final

    audit_results = calculate_trs_audit_final(df)

    # ===== COMPOSANTES CALCULÉES (moyennes simples) =====
    taux_dispo_calc = df["Do_Calc"].mean() if "Do_Calc" in df.columns else 0.0
    taux_perf_calc = df["Tp_Calc"].mean() if "Tp_Calc" in df.columns else 0.0
    taux_qualite_calc = df["Tq_Calc"].mean() if "Tq_Calc" in df.columns else 0.0

    # ===== TAUX ERP =====
    taux_dispo_erp = audit_results['do_erp']
    taux_perf_erp = audit_results['tp_erp']
    taux_qualite_erp = audit_results['tq_erp']

    # ===== TRS CALCULÉ (pondéré) =====
    if "TRS_Calc" in df.columns and len(df) > 0:
        tps_dispo = _get_tps_requis_series(df).fillna(8.0)
        trs_calc_values = df["TRS_Calc"].fillna(0)
        numerateur = (trs_calc_values * tps_dispo).sum()
        denominateur = tps_dispo.sum()
        trs_calc = numerateur / denominateur if denominateur > 0 else 0.0
    else:
        trs_calc = 0.0

    return {
        # TRS Principal (Audit)
        "trs_erp": audit_results['trs_erp'],
        "trs_réel": audit_results['trs_réel'],
        "trs_calc": trs_calc,

        # Écarts
        "écart_points": audit_results['écart_points'],
        "écart_pourcentage": audit_results['écart_pct'],

        # Composantes Réelles (Audit global)
        "taux_dispo_réel": audit_results['do_réel'],
        "taux_perf_réel": audit_results['tp_réel'],
        "taux_qualite_réel": audit_results['tq_réel'],

        # Composantes Calculées (moyennes)
        "taux_dispo_calc": taux_dispo_calc,
        "taux_perf_calc": taux_perf_calc,
        "taux_qualite_calc": taux_qualite_calc,

        # Composantes ERP
        "taux_dispo_erp": taux_dispo_erp,
        "taux_perf_erp": taux_perf_erp,
        "taux_qualite_erp": taux_qualite_erp,

        # Statistiques d'audit
        "lignes_production": audit_results['lignes_production'],
        "lignes_totales": audit_results['lignes_totales'],
        "lignes_zéro": audit_results['lignes_zéro'],

        # Rétrocompatibilité
        "delta_trs": audit_results['écart_points'],
    }
