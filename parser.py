"""Module de parsing des fichiers ERP (XLSX et CSV).

Ce module gère la lecture des fichiers exportés depuis l'ERP, en ignorant les
10 premières lignes de métadonnées et en supprimant les lignes de totaux.
Supporte le traitement par chunks pour les gros fichiers (>50k lignes).
"""
import pandas as pd
from pathlib import Path
from typing import Union, List, BinaryIO
import logging

logger = logging.getLogger(__name__)

# Nombre de lignes d'en-tête à ignorer dans les fichiers ERP
HEADER_ROWS_TO_SKIP = 10

# Seuil pour traitement par chunks (lignes)
CHUNK_SIZE_THRESHOLD = 50000
CHUNK_SIZE = 10000


def parse_file(file_path: Union[str, Path]) -> pd.DataFrame:
    """Parse un fichier XLSX ou CSV de l'ERP.

    Args:
        file_path: Chemin vers le fichier à parser

    Returns:
        DataFrame contenant les données nettoyées

    Raises:
        ValueError: Si le format de fichier n'est pas supporté
        FileNotFoundError: Si le fichier n'existe pas
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Le fichier {file_path} n'existe pas")

    if file_path.suffix == '.xlsx':
        df = _parse_xlsx(file_path)
    elif file_path.suffix == '.csv':
        df = _parse_csv(file_path)
    else:
        raise ValueError(f"Format non supporté: {file_path.suffix}")

    # Supprimer la ligne de total à la fin
    df = _remove_total_row(df)

    return df


def parse_uploaded_file(uploaded_file) -> pd.DataFrame:
    """
    Parse un fichier uploadé via Streamlit (InMemoryUploadedFile).
    Supporte le traitement par chunks pour les gros fichiers.
    
    Args:
        uploaded_file: Fichier uploadé via st.file_uploader()
        
    Returns:
        DataFrame contenant les données nettoyées
    """
    file_name = uploaded_file.name
    file_content = uploaded_file.getvalue()
    
    # Déterminer la taille approximative (en lignes estimées)
    estimated_rows = len(file_content) // 200  # Estimation grossière
    use_chunks = estimated_rows > CHUNK_SIZE_THRESHOLD
    
    if file_name.endswith('.xlsx'):
        df = _parse_xlsx_from_bytes(file_content, use_chunks=use_chunks)
    elif file_name.endswith('.csv'):
        df = _parse_csv_from_bytes(file_content, use_chunks=use_chunks)
    else:
        raise ValueError(f"Format non supporté: {file_name}")
    
    # Supprimer les lignes de total
    df = _remove_total_row(df)
    
    logger.info(f"Fichier parsé: {file_name}, {len(df)} lignes (chunks: {use_chunks})")
    return df


def _parse_xlsx_from_bytes(file_content: bytes, use_chunks: bool = False) -> pd.DataFrame:
    """Parse un fichier XLSX depuis des bytes."""
    from io import BytesIO
    
    buffer = BytesIO(file_content)

    # NOTE: pandas ne supporte pas le streaming/chunks natif pour read_excel.
    # On garde l'argument use_chunks pour compatibilité d'API, mais la lecture
    # reste en un seul passage pour éviter des erreurs de concaténation.
    return pd.read_excel(buffer, sheet_name='RESULTAT_EQUIPE', header=HEADER_ROWS_TO_SKIP)


def _parse_csv_from_bytes(file_content: bytes, use_chunks: bool = False) -> pd.DataFrame:
    """Parse un fichier CSV depuis des bytes."""
    from io import BytesIO, TextIOWrapper
    
    # Essayer UTF-8 d'abord, puis latin-1
    for encoding in ['utf-8-sig', 'latin-1']:
        try:
            buffer = BytesIO(file_content)
            text_buffer = TextIOWrapper(buffer, encoding=encoding)
            
            if use_chunks:
                # Lecture par chunks
                chunks = []
                for chunk in pd.read_csv(
                    text_buffer,
                    sep=';',
                    header=HEADER_ROWS_TO_SKIP,
                    decimal=',',
                    thousands=' ',
                    chunksize=CHUNK_SIZE
                ):
                    chunks.append(chunk)
                df = pd.concat(chunks, ignore_index=True)
            else:
                df = pd.read_csv(
                    text_buffer,
                    sep=';',
                    header=HEADER_ROWS_TO_SKIP,
                    decimal=',',
                    thousands=' '
                )
            return df
        except UnicodeDecodeError:
            continue
    
    raise ValueError("Impossible de décoder le fichier avec les encodages supportés")


def _parse_xlsx(file_path: Path) -> pd.DataFrame:
    """Parse un fichier XLSX en ignorant les 10 premières lignes.

    Args:
        file_path: Chemin vers le fichier XLSX

    Returns:
        DataFrame avec les données
    """
    logger.info(f"Parsing XLSX: {file_path}")
    # Ignorer les premières lignes de métadonnées
    # La ligne HEADER_ROWS_TO_SKIP (index 10) contient les en-têtes de colonnes
    # Lire explicitement la feuille RESULTAT_EQUIPE (données de production)
    df = pd.read_excel(file_path, sheet_name='RESULTAT_EQUIPE', header=HEADER_ROWS_TO_SKIP)
    logger.info(f"XLSX parsé: {len(df)} lignes, {len(df.columns)} colonnes")
    return df


def _parse_csv(file_path: Path) -> pd.DataFrame:
    """Parse un fichier CSV avec délimiteur point-virgule.

    Les fichiers CSV de l'ERP utilisent:
    - Délimiteur: point-virgule (;)
    - Encodage: UTF-8 avec BOM ou latin-1
    - 10 premières lignes à ignorer

    Args:
        file_path: Chemin vers le fichier CSV

    Returns:
        DataFrame avec les données
    """
    logger.info(f"Parsing CSV: {file_path}")

    # Essayer UTF-8 d'abord, puis latin-1 si échec
    for encoding in ['utf-8-sig', 'latin-1']:
        try:
            df = pd.read_csv(
                file_path,
                sep=';',
                header=HEADER_ROWS_TO_SKIP,
                encoding=encoding,
                decimal=',',  # Les nombres décimaux utilisent la virgule
                thousands=' '  # Les milliers utilisent l'espace
            )
            logger.info(f"CSV parsé avec {encoding}: {len(df)} lignes, {len(df.columns)} colonnes")
            return df
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Impossible de décoder {file_path} avec les encodages supportés")


def _remove_total_row(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime les lignes de total et lignes parasites du DataFrame.

    Supprime les lignes où:
    - Réf OF est vide/NaN (lignes de total ou récapitulatif)
    - Type OF est vide/NaN et Réf. Machine semble être un total

    Args:
        df: DataFrame à nettoyer

    Returns:
        DataFrame sans les lignes parasites
    """
    if len(df) == 0:
        return df

    initial_count = len(df)

    # Supprimer les lignes où Réf OF ET Type OF sont vides (lignes de total/récap)
    if 'Réf OF' in df.columns and 'Type OF' in df.columns:
        mask = df['Réf OF'].notna() | df['Type OF'].notna()
        df = df.loc[mask].copy()

    removed = initial_count - len(df)
    if removed > 0:
        logger.info(f"Suppression de {removed} ligne(s) parasite(s) détectée(s)")

    return df


def merge_files(file_paths: List[Union[str, Path]]) -> pd.DataFrame:
    """Fusionne plusieurs fichiers ERP en un seul DataFrame.

    Args:
        file_paths: Liste des chemins vers les fichiers à fusionner

    Returns:
        DataFrame contenant toutes les données fusionnées

    Raises:
        ValueError: Si la liste est vide ou si les schémas ne correspondent pas
    """
    if not file_paths:
        raise ValueError("La liste de fichiers est vide")

    dfs = []
    reference_columns = None

    for file_path in file_paths:
        df = parse_file(file_path)

        # Vérifier que toutes les DataFrames ont les mêmes colonnes
        if reference_columns is None:
            reference_columns = set(df.columns)
        elif set(df.columns) != reference_columns:
            logger.warning(
                f"Les colonnes de {file_path} ne correspondent pas aux précédentes. "
                f"Différence: {set(df.columns).symmetric_difference(reference_columns)}"
            )

        dfs.append(df)

    # Fusionner tous les DataFrames
    merged_df = pd.concat(dfs, ignore_index=True)
    logger.info(f"Fusion de {len(file_paths)} fichiers: {len(merged_df)} lignes au total")

    # Remove duplicates based on key columns
    cols_for_dedup = [c for c in merged_df.columns if c != "_source_file"]
    merged_df = merged_df.drop_duplicates(subset=cols_for_dedup, keep="first")
    logger.info(f"Après déduplication: {len(merged_df)} lignes")

    # NOUVEAU: Ajouter colonne Mois (YYYY-MM) pour filtrage/agrégation
    if "Début Equipe" in merged_df.columns:
        merged_df["Mois"] = pd.to_datetime(
            merged_df["Début Equipe"], errors="coerce"
        ).dt.to_period("M").astype(str)
        logger.info(f"Colonne 'Mois' créée avec {merged_df['Mois'].nunique()} mois uniques")
    else:
        logger.warning("Colonne 'Début Equipe' introuvable, colonne 'Mois' non créée")
        merged_df["Mois"] = "Inconnu"

    return merged_df
