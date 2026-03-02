"""
Interface Streamlit pour le mapping des colonnes.
"""
import streamlit as st
import pandas as pd
from column_mapper import ColumnMapper, REQUIRED_COLUMNS, suggest_column_mappings


def render_mapping_interface(df: pd.DataFrame, file_name: str) -> Dict[str, str]:
    """
    Affiche l'interface de mapping et retourne le mapping choisi.
    
    Returns:
        Dict[standard_col, file_col] ou None si annulé
    """
    mapper = ColumnMapper()
    
    # Vérifier si un mapping existe déjà pour cette source
    source_key = file_name.split('.')[0]  # Utilise le nom de fichier comme clé
    saved_mapping = mapper.load_mapping(source_key)
    
    if saved_mapping:
        st.success(f"✅ Mapping existant trouvé pour '{file_name}'")
        use_saved = st.checkbox("Utiliser le mapping sauvegardé", value=True)
        if use_saved:
            return saved_mapping
    
    # Détection automatique
    st.subheader("🔍 Détection automatique des colonnes")
    suggestion = suggest_column_mappings(df, mapper)
    
    confidence = suggestion["confidence"]
    if confidence >= 0.8:
        st.success(f"Confiance: {confidence:.0%} - Mapping automatique fiable")
    elif confidence >= 0.5:
        st.warning(f"Confiance: {confidence:.0%} - Veuillez vérifier le mapping")
    else:
        st.error(f"Confiance: {confidence:.0%} - Mapping manuel nécessaire")
    
    # Afficher les colonnes du fichier
    st.write("**Colonnes détectées dans le fichier:**")
    st.write(", ".join(df.columns.tolist()))
    
    # Interface de mapping
    st.subheader("🗺️ Mapping des colonnes")
    st.info("Associez chaque colonne requise à une colonne de votre fichier")
    
    mapping = {}
    available_columns = ["-- Ignorer --"] + df.columns.tolist()
    
    # Colonnes requises
    st.write("**Colonnes obligatoires:**")
    required_cols = {k: v for k, v in REQUIRED_COLUMNS.items() if v["required"]}
    
    for standard_col in required_cols.keys():
        # Valeur par défaut si détectée automatiquement
        default_idx = 0
        if standard_col in suggestion["detected_mapping"]:
            try:
                default_idx = available_columns.index(suggestion["detected_mapping"][standard_col])
            except ValueError:
                pass
        
        selected = st.selectbox(
            f"{standard_col}",
            options=available_columns,
            index=default_idx,
            key=f"map_{standard_col}"
        )
        
        if selected != "-- Ignorer --":
            mapping[standard_col] = selected
    
    # Colonnes optionnelles (dans un expander)
    with st.expander("Colonnes optionnelles"):
        optional_cols = {k: v for k, v in REQUIRED_COLUMNS.items() if not v["required"]}
        
        for standard_col in optional_cols.keys():
            default_idx = 0
            if standard_col in suggestion["detected_mapping"]:
                try:
                    default_idx = available_columns.index(suggestion["detected_mapping"][standard_col])
                except ValueError:
                    pass
            
            selected = st.selectbox(
                f"{standard_col} (optionnel)",
                options=available_columns,
                index=default_idx,
                key=f"map_opt_{standard_col}"
            )
            
            if selected != "-- Ignorer --":
                mapping[standard_col] = selected
    
    # Vérification
    missing = mapper.get_missing_columns(mapping)
    if missing:
        st.error(f"⚠️ Colonnes obligatoires manquantes: {', '.join(missing)}")
    else:
        st.success("✅ Toutes les colonnes obligatoires sont mappées!")
    
    # Boutons d'action
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Sauvegarder ce mapping", disabled=len(missing) > 0):
            mapper.save_mapping(source_key, mapping)
            st.success("Mapping sauvegardé pour les prochains fichiers similaires!")
            return mapping
    
    with col2:
        if st.button("▶️ Continuer sans sauvegarder", disabled=len(missing) > 0):
            return mapping
    
    return None


def show_mapping_summary(mapping: Dict[str, str]):
    """Affiche un résumé du mapping appliqué."""
    with st.expander("📋 Mapping appliqué"):
        data = []
        for standard, file_col in mapping.items():
            required = "Oui" if REQUIRED_COLUMNS.get(standard, {}).get("required", False) else "Non"
            data.append({"Standard": standard, "Fichier": file_col, "Obligatoire": required})
        
        st.table(pd.DataFrame(data))
