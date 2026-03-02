import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO

from parser import parse_uploaded_file, HEADER_ROWS_TO_SKIP
from calculator import calculate_all_metrics
from filters import apply_filters, calculate_aggregated_kpis, calculate_monthly_trs_table, calculate_filter_stats, calculate_filtered_stats
from exporter import export_to_excel

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="TRS Audit Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1.5 INITIALISATION SESSION STATE ---
if 'sidebar_always_open' not in st.session_state:
    st.session_state.sidebar_always_open = True

# --- 2. CSS PERSONNALISÉ ---
st.markdown("""
<style>
    /* Fond général */
    .stApp {
        background-color: #f8f9fa;
    }

    /* Style pour les KPIs circulaires du header */
    .kpi-circle {
        display: inline-block;
        text-align: center;
        margin: 0 20px;
    }

    .kpi-circle-label {
        font-size: 13px;
        color: #555;
        margin-top: 8px;
        font-weight: 500;
    }

    /* Header visible pour garder la flèche de la sidebar */
    header {
        visibility: visible;
    }

    /* Enlever les marges par défaut de Streamlit */
    .block-container {
        padding-top: 3rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* Style des sections */
    .section-title {
        font-size: 18px;
        font-weight: 600;
        color: #2c3e50;
        text-align: center;
        margin: 20px 0 15px 0;
        letter-spacing: 0.5px;
    }

    /* Amélioration de la sidebar */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }

    /* Espacement des éléments */
    .stMarkdown {
        margin-bottom: 0.5rem;
    }

    /* Style du divider - plus discret */
    hr {
        margin: 1rem 0;
        border: 0;
        border-top: 1px solid #f0f0f0;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FONCTIONS GRAPHIQUES ---

def create_circle_kpi(value, label):
    """Crée un KPI circulaire simple (pour le header)."""
    # Calcul du cercle (circonférence = 2πr)
    radius = 50
    circumference = 2 * 3.14159 * radius
    stroke_dasharray = f"{value * circumference} {circumference}"

    return f"""
    <div class="kpi-circle">
        <svg width="120" height="120" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="{radius}" fill="none" stroke="#e8eaed" stroke-width="8"/>
            <circle cx="60" cy="60" r="{radius}" fill="none" stroke="#0E60D7" stroke-width="8"
                    stroke-dasharray="{stroke_dasharray}"
                    transform="rotate(-90 60 60)" stroke-linecap="round"/>
            <text x="60" y="68" text-anchor="middle" font-size="22" font-weight="bold" fill="#0E60D7">
                {value*100:.1f}%
            </text>
        </svg>
        <div class="kpi-circle-label">{label}</div>
    </div>
    """

def create_ring_gauge(value, color="#0E60D7"):
    """Crée une jauge circulaire type ring (donut)."""
    fig = go.Figure()

    fig.add_trace(go.Pie(
        values=[value, 1 - value],
        hole=0.7,
        marker=dict(
            colors=[color, '#e8eaed'],
            line=dict(color='white', width=2)
        ),
        textinfo='none',
        hoverinfo='skip',
        showlegend=False
    ))

    # Annotation centrale avec pourcentage
    fig.add_annotation(
        text=f'<b>{value*100:.0f}%</b>',
        x=0.5, y=0.5,
        font=dict(size=28, color='#2c3e50', family='Arial'),
        showarrow=False
    )

    fig.update_layout(
        height=200,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    return fig

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown("### TRS Audit Tool")

    # Zone d'importation
    uploaded_files = st.file_uploader(
        "Importez vos fichiers ERP (XLSX, CSV)",
        accept_multiple_files=True,
        type=['xlsx', 'csv']
    )

    # Filtres
    st.markdown("#### Filtres")
    filter_config = {
        "include_sous_charge": st.checkbox("Inclure Sous-charge", value=True),
        "include_zero_trs": st.checkbox("Inclure TRS = 0", value=True),
        "include_anomalies": st.checkbox("Inclure Anomalies", value=True),
        "mois_selected": "Tous",
        "presse_selected": "Toutes",
        "outillage_selected": "Tous",
        "piece_selected": "Toutes",
    }

    # Section Stats (après import)
    stats_placeholder = st.container()

# --- 5. FONCTIONS CACHEES (Optimisation Performance) ---
@st.cache_data
def load_and_process_files(uploaded_files_data):
    """
    Charge et traite les fichiers uploadés avec support chunks.
    Cette fonction est mise en cache pour éviter de relire les fichiers
    à chaque interaction avec les filtres.
    """
    all_dfs = []
    for file_data in uploaded_files_data:
        file_name = file_data['name']
        file_content = file_data['content']
        
        # Utilisation de BytesIO pour simuler un fichier uploadé
        class MockUploadedFile:
            def __init__(self, name, content):
                self.name = name
                self._content = content
            
            def getvalue(self):
                return self._content
        
        mock_file = MockUploadedFile(file_name, file_content)
        df = parse_uploaded_file(mock_file)
        all_dfs.append(df)

    raw_df = pd.concat(all_dfs, ignore_index=True)

    if "Début Equipe" in raw_df.columns:
        raw_df["Mois"] = pd.to_datetime(raw_df["Début Equipe"], errors="coerce").dt.to_period("M").astype(str)
    else:
        raw_df["Mois"] = "Inconnu"

    # Calculs métriques (une seule fois)
    processed_df = calculate_all_metrics(raw_df)
    
    return processed_df


# --- 6. LOGIQUE PRINCIPALE ---
if uploaded_files:
    try:
        # A. Préparation des données pour le cache (conversion en bytes)
        uploaded_files_data = []
        for uploaded_file in uploaded_files:
            uploaded_files_data.append({
                'name': uploaded_file.name,
                'content': uploaded_file.getvalue()
            })
        
        # B. Chargement et traitement (avec cache + parser chunks)
        processed_df = load_and_process_files(uploaded_files_data)

        # C. Filtres Avancés (après import)
        with st.sidebar:
            st.markdown("#### Filtres Avancés")

            # 1. Mois
            unique_mois = ["Tous"] + sorted(processed_df["Mois"].dropna().unique().tolist())
            filter_config["mois_selected"] = st.selectbox("Mois", unique_mois)

            # Fonction utilitaire pour nettoyer les IDs (606.0 -> "606")
            def get_clean_id(x):
                if pd.isna(x): return None
                try:
                    if float(x).is_integer():
                        return str(int(float(x)))
                    return str(x)
                except:
                    return str(x)

            def clean_options(series):
                cleaned = series.apply(get_clean_id).dropna().unique()
                return sorted([str(x) for x in cleaned])

            # 2. Presse
            if "Réf. Machine" in processed_df.columns:
                unique_presse = ["Toutes"] + clean_options(processed_df["Réf. Machine"])
                filter_config["presse_selected"] = st.selectbox("Presse", unique_presse)

            # Filtrage dynamique: Outillage/Pièce dépendent de la Presse
            temp_df = processed_df.copy()
            if "Réf. Machine" in temp_df.columns and filter_config["presse_selected"] != "Toutes":
                temp_df = temp_df[temp_df["Réf. Machine"].apply(get_clean_id) == filter_config["presse_selected"]]

            # 3. Outillage
            if "Réf. outil" in temp_df.columns:
                unique_outils = ["Tous"] + clean_options(temp_df["Réf. outil"])
                filter_config["outillage_selected"] = st.selectbox("Outillage", unique_outils)

            # 4. Pièce
            if "Réf. produit" in temp_df.columns:
                unique_produits = ["Toutes"] + clean_options(temp_df["Réf. produit"])
                filter_config["piece_selected"] = st.selectbox("Pièce", unique_produits)

        # D. Filtrage et KPIs
        filtered_df = apply_filters(processed_df, filter_config)
        kpis = calculate_aggregated_kpis(filtered_df)
        # Stats calculées sur les données FILTRÉES (pas sur les données brutes)
        stats = calculate_filtered_stats(filtered_df, processed_df)
        monthly_df = calculate_monthly_trs_table(filtered_df)

        # E. Stats dans sidebar (actualisées selon les filtres)
        with stats_placeholder:
            st.markdown("#### Stats")
            st.text(f"Lignes totales:    {stats['total_rows']}")
            st.text(f"Lignes affichées:  {stats['filtered_rows']}")
            st.text(f"Actives (TRS>0):   {stats['active_count']}")
            st.text(f"À 0 (TRS=0):       {stats['zero_trs_count']}")
            st.text(f"Anomalies:         {stats['anomaly_count']}")

        # F. Bouton Export Excel
        with st.sidebar:
            buffer = export_to_excel(filtered_df, monthly_df)

            st.download_button(
                label="Exporter Excel",
                data=buffer.getvalue(),
                file_name="Rapport_Audit_TRS.xlsx",
                mime="application/vnd.ms-excel",
                type="primary",
                use_container_width=True
            )

        # --- 6. AFFICHAGE PRINCIPAL ---

        # Message d'aide - si sidebar fermée
        st.info("💡 **Astuce:** Si la barre latérale est fermée, cliquez sur la flèche **>** en haut à gauche pour la rouvrir et accéder aux filtres.", icon="ℹ️")

        # HEADER - 5 KPIs circulaires
        col_spacer1, kpi1, kpi2, kpi3, kpi4, kpi5, col_spacer2 = st.columns([0.5, 1, 1, 1, 1, 1, 0.5])

        with kpi1:
            st.markdown(create_circle_kpi(kpis['trs_erp'], "TRS ERP"), unsafe_allow_html=True)
        with kpi2:
            st.markdown(create_circle_kpi(kpis['trs_réel'], "TRS Réel"), unsafe_allow_html=True)
        with kpi3:
            st.markdown(create_circle_kpi(kpis['écart_points'], "Écart"), unsafe_allow_html=True)
        with kpi4:
            active_pct = stats['ok_percentage'] / 100
            st.markdown(create_circle_kpi(active_pct, "% Lignes Actives"), unsafe_allow_html=True)
        with kpi5:
            nok_pct = stats['anomaly_percentage'] / 100
            st.markdown(create_circle_kpi(nok_pct, "% Lignes NOK"), unsafe_allow_html=True)

        # SECTION TAUX ERP
        st.markdown('<div class="section-title">Taux ERP</div>', unsafe_allow_html=True)

        col_spacer1, c1, c2, c3, col_spacer2 = st.columns([0.3, 1, 1, 1, 0.3])
        with c1:
            st.plotly_chart(create_ring_gauge(kpis['taux_dispo_erp'], "#0E60D7"), use_container_width=True, key="gauge_erp_dispo")
            st.markdown("<div style='text-align:center; font-size:14px; font-weight:bold; color:#555;'>Disponibilité</div>", unsafe_allow_html=True)
        with c2:
            st.plotly_chart(create_ring_gauge(kpis['taux_perf_erp'], "#0E60D7"), use_container_width=True, key="gauge_erp_perf")
            st.markdown("<div style='text-align:center; font-size:14px; font-weight:bold; color:#555;'>Performance</div>", unsafe_allow_html=True)
        with c3:
            st.plotly_chart(create_ring_gauge(kpis['taux_qualite_erp'], "#0E60D7"), use_container_width=True, key="gauge_erp_qualite")
            st.markdown("<div style='text-align:center; font-size:14px; font-weight:bold; color:#555;'>Qualité</div>", unsafe_allow_html=True)

        # SECTION TAUX RÉELS (Calculés)
        st.markdown('<div class="section-title">Taux Réels (Calculés)</div>', unsafe_allow_html=True)

        col_spacer1, c1, c2, c3, col_spacer2 = st.columns([0.3, 1, 1, 1, 0.3])
        with c1:
            st.plotly_chart(create_ring_gauge(kpis['taux_dispo_réel'], "#0E60D7"), use_container_width=True, key="gauge_reel_dispo")
            st.markdown("<div style='text-align:center; font-size:14px; font-weight:bold; color:#555;'>Disponibilité</div>", unsafe_allow_html=True)
        with c2:
            st.plotly_chart(create_ring_gauge(kpis['taux_perf_réel'], "#0E60D7"), use_container_width=True, key="gauge_reel_perf")
            st.markdown("<div style='text-align:center; font-size:14px; font-weight:bold; color:#555;'>Performance</div>", unsafe_allow_html=True)
        with c3:
            st.plotly_chart(create_ring_gauge(kpis['taux_qualite_réel'], "#0E60D7"), use_container_width=True, key="gauge_reel_qualite")
            st.markdown("<div style='text-align:center; font-size:14px; font-weight:bold; color:#555;'>Qualité</div>", unsafe_allow_html=True)

        # GRAPHIQUE
        st.markdown(f'<div class="section-title">Évolution TRS par Mois | Global: ERP {kpis["trs_erp"]*100:.1f}% - Réel {kpis["trs_réel"]*100:.1f}%</div>', unsafe_allow_html=True)

        if not monthly_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=monthly_df["Mois"],
                y=monthly_df["TRS_ERP"]*100,
                mode='lines+markers',
                name='TRS ERP',
                line=dict(color='#0E60D7', width=3),
                marker=dict(size=8, symbol='circle')
            ))
            fig.add_trace(go.Scatter(
                x=monthly_df["Mois"],
                y=monthly_df["TRS_Réel"]*100,
                mode='lines+markers',
                name='TRS Réel',
                line=dict(color='#7CB9E8', width=3),
                marker=dict(size=8, symbol='circle')
            ))
            fig.update_layout(
                height=400,
                margin=dict(l=50, r=50, t=30, b=50),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='white',
                yaxis=dict(
                    title="TRS (%)",
                    range=[0, 100],
                    gridcolor='#e8eaed',
                    title_font=dict(size=14, color='#555')
                ),
                xaxis=dict(
                    title="",
                    gridcolor='#e8eaed',
                    title_font=dict(size=14, color='#555')
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    font=dict(size=13)
                ),
                font=dict(family='Arial', size=12)
            )
            st.plotly_chart(fig, use_container_width=True, key="evolution_trs_main_chart")
        else:
            st.info("Pas de données temporelles.")

        # TABLEAU
        st.markdown('<div class="section-title">📊 TRS par Mois (Pondéré vs ERP)</div>', unsafe_allow_html=True)
        st.dataframe(
            monthly_df[["Mois", "TRS_Réel", "TRS_ERP", "Écart"]].style.format({
                "TRS_Réel": "{:.1%}",
                "TRS_ERP": "{:.1%}",
                "Écart": "{:.2f}"
            }),
            use_container_width=True,
            height=350
        )

    except Exception as e:
        st.error(f"Erreur d'analyse : {e}")
        st.code(str(e))

else:
    # Ecran d'accueil vide
    st.markdown("""
    <div style='text-align: center; padding: 50px; color: #888;'>
        <h2>📋 Application TRS Audit Dashboard</h2>
        <p style='font-size: 16px;'>Bienvenue dans l'outil d'audit du Taux de Rendement Synthétique.</p>
    </div>
    """, unsafe_allow_html=True)
