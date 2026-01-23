"""Module d'export Excel avec mise en forme professionnelle."""
import pandas as pd
from pathlib import Path
from typing import Union
from io import BytesIO


def _create_audit_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Crée le tableau récapitulatif de l'audit TRS."""
    try:
        from calculator import calculate_trs_audit_final
    except ImportError:
        from .calculator import calculate_trs_audit_final

    if df.empty:
        return pd.DataFrame({
            "Métrique": ["Aucune donnée"],
            "Valeur": ["N/A"]
        })

    audit = calculate_trs_audit_final(df)

    tps_dispo_total = df['Tps Disponible (h)'].sum() if 'Tps Disponible (h)' in df.columns else 0.0
    tps_utile_total = df['Tps Utile (h)'].sum() if 'Tps Utile (h)' in df.columns else 0.0

    data = [
        ["AUDIT TRS : CAPACITÉ RÉELLE vs DÉCLARÉE", ""],
        ["", ""],
        ["RÉSULTATS GLOBAUX", ""],
        ["Temps Disponible Total (h)", f"{tps_dispo_total:,.0f}"],
        ["Temps Utile Total (h)", f"{tps_utile_total:,.0f}"],
        ["", ""],
        ["TRS ERP (Moyenne, exclut zéros)", f"{audit['trs_erp']*100:.2f}%"],
        ["TRS Réel (Global, inclut tout)", f"{audit['trs_réel']*100:.2f}%"],
        ["", ""],
        ["ÉCART IDENTIFIÉ", ""],
        ["Écart (points)", f"{audit['écart_points']*100:+.2f}"],
        ["Surestimation ERP (%)", f"{audit['écart_pct']:.1f}%"],
        ["", ""],
        ["COMPOSANTES DU TRS RÉEL", ""],
        ["Disponibilité (Do)", f"{audit['do_réel']*100:.2f}%"],
        ["Performance (Tp)", f"{audit['tp_réel']*100:.2f}%"],
        ["Qualité (Tq)", f"{audit['tq_réel']*100:.2f}%"],
        ["", ""],
        ["STATISTIQUES", ""],
        ["Lignes Totales", f"{audit['lignes_totales']:,}"],
        ["Lignes avec Production", f"{audit['lignes_production']:,}"],
        ["Lignes Sans Production (zéros)", f"{audit['lignes_zéro']:,}"],
        ["Pourcentage Inactivité", f"{(audit['lignes_zéro']/audit['lignes_totales']*100 if audit['lignes_totales'] > 0 else 0):.1f}%"],
    ]

    return pd.DataFrame(data, columns=["Métrique", "Valeur"])


def _create_synthese(df: pd.DataFrame) -> pd.DataFrame:
    """Crée le tableau de synthèse par machine."""
    if df.empty or "Réf. Machine" not in df.columns:
        return pd.DataFrame(columns=["Machine", "TRS_ERP", "TRS_Calculé", "Écart"])

    trs_col = None
    if "TRS_Calc" in df.columns:
        trs_col = "TRS_Calc"
    elif "TRS_Réel" in df.columns:
        trs_col = "TRS_Réel"
    elif "trs_reel" in df.columns:
        trs_col = "trs_reel"

    if trs_col and "T.R.S." in df.columns:
        grouped = df.groupby("Réf. Machine").agg({
            "T.R.S.": "mean",
            trs_col: "mean",
        }).round(4)
        grouped.columns = ["TRS_ERP", "TRS_Calculé"]
        grouped["Écart"] = grouped["TRS_ERP"] - grouped["TRS_Calculé"]
        return grouped

    return pd.DataFrame(columns=["TRS_ERP", "TRS_Calculé", "Écart"])


def _create_alertes(df: pd.DataFrame) -> pd.DataFrame:
    """Crée le tableau des alertes (anomalies)."""
    if df.empty or "is_anomaly" not in df.columns:
        return pd.DataFrame(columns=["Machine", "OF", "Date", "Type_Anomalie", "TRS_ERP", "TRS_Calculé"])

    anomalies_df = df[df["is_anomaly"] == True].copy()

    if anomalies_df.empty:
        return pd.DataFrame(columns=["Machine", "OF", "Date", "Type_Anomalie", "TRS_ERP", "TRS_Calculé"])

    trs_calc_col = None
    if "TRS_Calc" in anomalies_df.columns:
        trs_calc_col = "TRS_Calc"
    elif "TRS_Réel" in anomalies_df.columns:
        trs_calc_col = "TRS_Réel"
    elif "trs_reel" in anomalies_df.columns:
        trs_calc_col = "trs_reel"

    result = pd.DataFrame({
        "Machine": anomalies_df.get("Réf. Machine", ""),
        "OF": anomalies_df.get("Réf OF", ""),
        "Date": anomalies_df.get("Début Equipe", ""),
        "Type_Anomalie": anomalies_df["anomalies"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else str(x)
        ),
        "TRS_ERP": anomalies_df.get("T.R.S.", 0),
        "TRS_Calculé": anomalies_df.get(trs_calc_col, 0) if trs_calc_col else 0,
    })

    return result.reset_index(drop=True)


def export_to_excel(
    filtered_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    output_path: Union[str, Path] = None,
) -> BytesIO:
    """
    Exporte les données vers un fichier Excel avec tous les onglets.

    Onglets:
    1. Audit_TRS: Résumé exécutif avec écarts
    2. Synthèse: Tableau par machine
    3. Alertes: Anomalies détectées
    4. Synthèse_Mensuelle: TRS par mois
    5. Données_Audit: Dataset complet avec colonnes calculées

    Args:
        filtered_df: DataFrame filtré avec données ERP + colonnes calculées
        monthly_df: DataFrame avec résumé mensuel
        output_path: Optionnel. Si fourni, écrit sur disque. Sinon retourne BytesIO.

    Returns:
        BytesIO (pour streaming Streamlit) ou Path (si output_path fourni)
    """
    if output_path:
        buffer = open(output_path, 'wb')
    else:
        buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book

        # === Onglet 1: Audit TRS (Résumé exécutif) ===
        audit_df = _create_audit_summary(filtered_df)
        audit_df.to_excel(writer, sheet_name="Audit_TRS", index=False)
        ws_audit = writer.sheets["Audit_TRS"]
        ws_audit.set_column("A:A", 35)
        ws_audit.set_column("B:B", 25)

        # === Onglet 2: Synthèse par Machine ===
        synthese_df = _create_synthese(filtered_df)
        synthese_df.to_excel(writer, sheet_name="Synthèse")
        ws_synthese = writer.sheets["Synthèse"]
        ws_synthese.set_column("A:A", 15)
        ws_synthese.set_column("B:D", 15)

        # === Onglet 3: Alertes (Anomalies) ===
        alertes_df = _create_alertes(filtered_df)
        alertes_df.to_excel(writer, sheet_name="Alertes", index=False)
        ws_alertes = writer.sheets["Alertes"]
        ws_alertes.set_column("A:F", 18)

        # === Onglet 4: Synthèse Mensuelle ===
        if not monthly_df.empty:
            monthly_df.to_excel(writer, sheet_name="Synthèse_Mensuelle", index=False)
            ws_monthly = writer.sheets["Synthèse_Mensuelle"]
            ws_monthly.set_column("A:E", 15)

        # === Onglet 5: Données Complètes ===
        erp_cols = [c for c in filtered_df.columns
                   if not c.endswith('_Calc')
                   and c not in ['TRS_Écart', 'TRS_ERP_Surestime', 'tps_net_h',
                                'taux_dispo_reel', 'taux_perf_reel', 'taux_qualite_reel',
                                'trs_reel']]
        calc_cols = ['Do_Calc', 'Tp_Calc', 'Tq_Calc', 'TRS_Calc', 'TRS_Écart']
        meta_cols = ['is_anomaly', 'anomalies']

        final_cols = (erp_cols +
                     [c for c in calc_cols if c in filtered_df.columns] +
                     [c for c in meta_cols if c in filtered_df.columns])

        data_df = filtered_df[final_cols].copy()

        if "anomalies" in data_df.columns:
            data_df["anomalies"] = data_df["anomalies"].apply(
                lambda x: ", ".join(x) if isinstance(x, list) else str(x)
            )

        data_df.to_excel(writer, sheet_name="Données_Audit", index=False)
        ws_data = writer.sheets["Données_Audit"]
        ws_data.set_column("A:Z", 13)
        ws_data.autofilter(0, 0, len(data_df), len(final_cols) - 1)

    if output_path:
        buffer.close()
        return Path(output_path)
    else:
        buffer.seek(0)
        return buffer
