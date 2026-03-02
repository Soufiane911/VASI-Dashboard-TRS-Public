"""
Module de mapping intelligent des colonnes.
Permet d'adapter n'importe quelle structure de fichier ERP aux colonnes attendues.
"""
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, List
from difflib import SequenceMatcher

# Colonnes REQUISES par l'application (standard interne)
REQUIRED_COLUMNS = {
    "Début Equipe": {"types": ["datetime", "object"], "required": True},
    "Réf. Machine": {"types": ["object", "float", "int"], "required": True},
    "Type OF": {"types": ["object"], "required": True},
    "T.R.S.": {"types": ["float", "int", "object"], "required": True},
    "Tps Fct Brut (h)": {"types": ["float", "int"], "required": True},
    "Tps Disponible (h)": {"types": ["float", "int"], "required": True},
    "Tps Utile (h)": {"types": ["float", "int"], "required": True},
    "Nb Cycles": {"types": ["int", "float"], "required": True},
    "Cycle Théo": {"types": ["float", "int"], "required": True},
    "Qté Pieces Fab.": {"types": ["int", "float"], "required": True},
    "Qté Pieces Bonnes": {"types": ["int", "float"], "required": True},
    # Colonnes optionnelles
    "Réf OF": {"types": ["object"], "required": False},
    "Réf. outil": {"types": ["object"], "required": False},
    "Réf. produit": {"types": ["object"], "required": False},
    "Lib. Machine": {"types": ["object"], "required": False},
    "Taux Performance": {"types": ["float", "int", "object"], "required": False},
    "Taux Qualité": {"types": ["float", "int", "object"], "required": False},
    "Total Rebuts": {"types": ["int", "float"], "required": False},
}

# Synonymes connus pour la détection automatique
COLUMN_SYNONYMS = {
    "Début Equipe": ["date", "datetime", "debut", "start", "heure", "timestamp", "period"],
    "Réf. Machine": ["machine", "presse", "equipement", "ref machine", "machine_id", "id_machine"],
    "Type OF": ["type", "type_of", "ordre", "of_type", "category"],
    "T.R.S.": ["trs", "taux rendement", "synthetic yield", "performance_rate", "trs_erp"],
    "Tps Fct Brut (h)": ["temps fonctionnement", "running time", "operating hours", "brut", "gross time"],
    "Tps Disponible (h)": ["temps dispo", "available time", "disponible", "open time"],
    "Tps Utile (h)": ["temps utile", "useful time", "net time", "productive time"],
    "Nb Cycles": ["cycles", "nombre cycles", "cycle count", "nb_cycles", "cycle_number"],
    "Cycle Théo": ["cycle theorique", "theoretical cycle", "cycle_time", "temps cycle"],
    "Qté Pieces Fab.": ["pieces fabriquees", "quantite", "quantity produced", "output", "production"],
    "Qté Pieces Bonnes": ["pieces bonnes", "good parts", "conforme", "good quantity", "ok parts"],
    "Réf OF": ["of", "ordre fabrication", "work order", "production order", "job"],
    "Réf. outil": ["outil", "tool", "mold", "moule", "tool_id"],
    "Réf. produit": ["produit", "piece", "part", "product", "part_id", "reference"],
}


class ColumnMapper:
    """Gère le mapping entre les colonnes du fichier et les colonnes standard."""
    
    def __init__(self, mapping_file: str = "column_mappings.json"):
        self.mapping_file = Path(mapping_file)
        self.mappings = self._load_mappings()
    
    def _load_mappings(self) -> Dict:
        """Charge les mappings sauvegardés."""
        if self.mapping_file.exists():
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_mappings(self):
        """Sauvegarde les mappings."""
        with open(self.mapping_file, 'w', encoding='utf-8') as f:
            json.dump(self.mappings, f, indent=2, ensure_ascii=False)
    
    def detect_mapping(self, df: pd.DataFrame, threshold: float = 0.7) -> Dict[str, str]:
        """
        Détecte automatiquement le mapping basé sur la similarité des noms.
        
        Returns:
            Dict[mapping_key, colonne_detectee]
        """
        detected = {}
        used_columns = set()
        
        for standard_col, config in REQUIRED_COLUMNS.items():
            best_match = None
            best_score = 0
            
            for file_col in df.columns:
                if file_col in used_columns:
                    continue
                
                # Score de similarité avec le nom standard
                score = SequenceMatcher(None, standard_col.lower(), file_col.lower()).ratio()
                
                # Score avec les synonymes
                for synonym in COLUMN_SYNONYMS.get(standard_col, []):
                    syn_score = SequenceMatcher(None, synonym.lower(), file_col.lower()).ratio()
                    score = max(score, syn_score)
                
                # Vérification du type
                if score > best_score and score >= threshold:
                    if self._check_type_compatibility(df[file_col], config["types"]):
                        best_score = score
                        best_match = file_col
            
            if best_match:
                detected[standard_col] = best_match
                used_columns.add(best_match)
        
        return detected
    
    def _check_type_compatibility(self, series: pd.Series, expected_types: List[str]) -> bool:
        """Vérifie si le type de données est compatible."""
        actual_type = series.dtype.name.lower()
        
        for expected in expected_types:
            if expected in actual_type:
                return True
            # Cas spéciaux
            if expected == "datetime" and ("datetime" in actual_type or series.name.lower() in ["date", "debut"]):
                return True
        return False
    
    def get_confidence_score(self, detected_mapping: Dict[str, str]) -> float:
        """Calcule le score de confiance du mapping détecté."""
        required_count = sum(1 for v in REQUIRED_COLUMNS.values() if v["required"])
        detected_required = sum(1 for k in detected_mapping.keys() if REQUIRED_COLUMNS.get(k, {}).get("required", False))
        return detected_required / required_count if required_count > 0 else 0
    
    def apply_mapping(self, df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """Applique le mapping au DataFrame."""
        # Renommer les colonnes
        reverse_mapping = {v: k for k, v in mapping.items()}
        df_mapped = df.rename(columns=reverse_mapping)
        
        # S'assurer que toutes les colonnes requises existent (même vides)
        for col in REQUIRED_COLUMNS.keys():
            if col not in df_mapped.columns:
                df_mapped[col] = 0 if "Qté" in col or "Tps" in col or "Nb" in col else None
        
        return df_mapped
    
    def save_mapping(self, source_name: str, mapping: Dict[str, str]):
        """Sauvegarde un mapping pour une source donnée."""
        self.mappings[source_name] = mapping
        self._save_mappings()
    
    def load_mapping(self, source_name: str) -> Optional[Dict[str, str]]:
        """Charge un mapping sauvegardé."""
        return self.mappings.get(source_name)
    
    def get_missing_columns(self, mapping: Dict[str, str]) -> List[str]:
        """Retourne les colonnes requises manquantes."""
        missing = []
        for col, config in REQUIRED_COLUMNS.items():
            if config["required"] and col not in mapping:
                missing.append(col)
        return missing


def suggest_column_mappings(df: pd.DataFrame, mapper: ColumnMapper) -> Dict:
    """
    Fonction utilitaire pour suggérer les mappings avec confiance.
    """
    detected = mapper.detect_mapping(df)
    confidence = mapper.get_confidence_score(detected)
    missing = mapper.get_missing_columns(detected)
    
    return {
        "detected_mapping": detected,
        "confidence": confidence,
        "missing_required": missing,
        "is_complete": len(missing) == 0
    }
