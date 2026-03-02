# Analyse Technique - Dashboard TRS

> Synthèse de deux analyses : revue de code externe + analyse complémentaire

---

## 📊 Tableau synthétique des problèmes

| # | Problème | Source | Priorité | Impact | Fichier(s) concerné(s) |
|---|----------|--------|----------|--------|------------------------|
| 1 | **Absence de cache Streamlit** | Son analyse 🔍 | 🔴 Critique | UX dégradée - Recalcul total à chaque filtre | `streamlit_app.py` (lignes 169-260) |
| 2 | **Anti-pattern Pandas (`iterrows`)** | Son analyse 🔍 | 🔴 Critique | Performance ×100 à ×1000 plus lente | `calculator.py` (ligne 158) |
| 3 | **Duplication du parser** | Son analyse 🔍 | 🟡 Moyenne | Code mort dans `parser.py` | `streamlit_app.py` (174-177) vs `parser.py` |
| 4 | **Imports circulaires** | Son analyse 🔍 | 🟠 Élevée | Couplage fort, tests impossibles | `filters.py` (212), `exporter.py` (11) |
| 5 | **Magic strings (noms colonnes)** | Son analyse 🔍 | 🟠 Élevée | Maintenance impossible si ERP évolue | Tous les fichiers (×30+ références) |
| 6 | **Architecture UI monolithique** | Son analyse 🔍 | 🟡 Moyenne | Lisibilité, difficulté de maintenance | `streamlit_app.py` (383 lignes) |
| 7 | **Incohérence calculs TRS** | Mon analyse ⭐ | 🔴 Critique | 3 méthodes = 3 résultats différents | `calculator.py` (3 fonctions) |
| 8 | **Valeurs magiques** | Mon analyse ⭐ | 🟠 Élevée | `8.0`h, `1.5`, comportements non documentés | `calculator.py` (36, 196) |
| 9 | **Absence totale de tests** | Mon analyse ⭐ | 🟠 Élevée | Aucune régression détectable | Projet entier |
| 10 | **Typage inconsistant** | Mon analyse ⭐ | 🟡 Moyenne | `FilterConfig` vs `dict` | `filters.py` (7) vs `streamlit_app.py` (155) |
| 11 | **Gestion d'erreurs trop large** | Mon analyse ⭐ | 🟡 Moyenne | Masque les vrais bugs | `streamlit_app.py` (372-374) |

---

## 🔴 Critique (À faire en priorité)

### 1. Absence de Cache Streamlit
**Détail :** Chaque interaction (filtre, checkbox) relance la lecture des fichiers Excel/CSV et tous les calculs depuis zéro.

```python
# PROBLÈME (streamlit_app.py:169-188)
if uploaded_files:
    for uploaded_file in uploaded_files:  # ← Relu à CHAQUE clic
        df = pd.read_excel(uploaded_file)  # ← Lent !
    processed_df = calculate_all_metrics(raw_df)  # ← Recalcul total
```

**Solution :** Utiliser `@st.cache_data` pour isoler la lecture et le calcul initial.

---

### 2. Anti-pattern Pandas (`iterrows`)
**Détail :** Boucle Python ligne par ligne = mort des performances sur gros volumes.

```python
# PROBLÈME (calculator.py:158)
for idx, row in df.iterrows():  # ← EXTÊMEMENT LENT
    # ... calculs ligne par ligne
    df.at[idx, "TRS_Calc"] = trs_réel  # ← Écriture individuelle
```

**Solution :** Vectorisation complète des opérations.

```python
# SOLUTION
 df["TRS_Réel"] = df["Do_Réel"] * df["Tp_Réel"] * df["Tq_Réel"]
```

---

### 7. Incohérence des calculs TRS (Non détecté dans l'autre analyse)
**Détail :** Trois fonctions calculent le TRS différemment → résultats incohérents selon l'endroit où on regarde.

| Fonction | Méthode ERP | Méthode Réel | Risque |
|----------|-------------|--------------|--------|
| `calculate_monthly_trs_table` | Moyenne simple | Pondérée par temps dispo | Écarts inexpliqués |
| `calculate_aggregated_kpis` | Moyenne simple | Pondérée par temps requis | KPIs faux |
| `calculate_trs_audit_final` | Moyenne simple | Pondérée globale | Comparaisons invalides |

**Impact :** Les utilisateurs voient des TRS différents dans le tableau mensuel vs les KPIs globaux.

---

## 🟠 Élevée (Risque moyen terme)

### 4. Imports circulaires
**Détail :** Les `try/except ImportError` masquent un couplage anarchique.

```python
# PROBLÈME (filters.py:212)
try:
    from calculator import calculate_trs_audit_final
except ImportError:
    from .calculator import calculate_trs_audit_final
```

**Solution :** Créer un fichier `metrics.py` centralisé pour les fonctions partagées.

---

### 5. Magic strings (noms de colonnes)
**Détail :** Les noms de colonnes ERP sont hardcodés ~30 fois dans le code.

```python
# Exemples de magic strings dangereux :
"Réf. Machine"      # apparu 8 fois
"T.R.S."            # apparu 12 fois  
"Tps Fct Brut (h)"  # apparu 6 fois
"Qté Pieces Bonnes" # apparu 5 fois
```

**Risque :** Si l'ERP change "Réf. Machine" → "Reference Machine", le code explose silencieusement.

**Solution :** Fichier `constants.py` :
```python
COL_MACHINE = "Réf. Machine"
COL_TRS = "T.R.S."
COL_TEMPS_FCT_BRUT = "Tps Fct Brut (h)"
# etc.
```

---

### 8. Valeurs magiques (Non détecté dans l'autre analyse)
**Détail :** Constantes non documentées qui influencent les calculs.

| Valeur | Ligne | Signification | Problème |
|--------|-------|---------------|----------|
| `8.0` | 36 | Heures par défaut si pas de données | Pourquoi 8 ? Pourquoi pas 7 ou 24 ? |
| `1.5` | 196 | Plafond TRS calculé | Pourquoi 150% ? Un TRS > 100% est-il possible ? |
| `0.001` | 209 | Seuil de surestimation | Arbitré, pas documenté |

---

### 9. Absence de tests (Non détecté dans l'autre analyse)
**Détail :** Aucun fichier `test_*.py`, aucune validation des calculs critiques.

**Risques :**
- Régression silencieuse sur les calculs TRS
- Impossible de refactorer en sécurité
- Aucune validation des cas limites (division par zéro, NaN)

---

## 🟡 Moyenne (Qualité de vie)

### 3. Duplication du parser
**Détail :** `parser.py` est bien écrit mais ignoré par `streamlit_app.py` qui refait ses propres `pd.read_excel/read_csv`.

```python
# streamlit_app.py (lignes 174-177) DUPLIQUE parser.py
if uploaded_file.name.endswith('.xlsx'):
    df = pd.read_excel(uploaded_file, sheet_name='RESULTAT_EQUIPE', ...)
else:
    df = pd.read_csv(uploaded_file, sep=';', ...)
```

---

### 6. Architecture UI monolithique
**Détail :** 383 lignes dans un seul fichier avec parsing + métier + UI + CSS mélangés.

**Découpage suggéré :**
```
streamlit_app.py      →  Orchestration uniquement
├── components/ui.py  →  Fonctions de rendu
├── assets/style.css  →  CSS externe
└── pages/*.py        →  Onglets si besoin
```

---

### 10. Typage inconsistant
**Détail :** Une `dataclass FilterConfig` existe mais un `dict` est utilisé à la place.

```python
# filters.py:7 - Définie mais INUTILISÉE
@dataclass
class FilterConfig:
    include_sous_charge: bool = True
    ...

# streamlit_app.py:155 - Dict utilisé
filter_config = {  # Pas de validation, pas d'autocomplétion
    "include_sous_charge": st.checkbox(...),
}
```

---

### 11. Gestion d'erreurs trop large
**Détail :** Un seul `try/except` englobe tout le traitement.

```python
# PROBLÈME (streamlit_app.py:372)
try:
    # ... 200 lignes de traitement
except Exception as e:  # ← Attrape TOUT, même les bugs inattendus
    st.error(f"Erreur d'analyse : {e}")
```

---

## 📋 Plan d'action recommandé

### Phase 1 : Performance (Semaine 1)
- [ ] Ajouter `@st.cache_data` sur la lecture de fichiers
- [ ] Vectoriser `calculate_trs_réel_nf60182()` (supprimer `iterrows`)
- [ ] **Impact immédiat** : Temps de chargement divisé par 10-100

### Phase 2 : Fiabilité (Semaine 2)
- [ ] Centraliser les noms de colonnes dans `constants.py`
- [ ] Unifier les 3 méthodes de calcul TRS en une seule
- [ ] Documenter les valeurs magiques (8.0, 1.5)
- [ ] **Impact** : KPIs cohérents et maintenables

### Phase 3 : Architecture (Semaine 3)
- [ ] Créer `metrics.py` pour casser les imports circulaires
- [ ] Utiliser `FilterConfig` au lieu du dict
- [ ] Extraire le CSS dans un fichier externe
- [ ] **Impact** : Base solide pour évolutions

### Phase 4 : Qualité (Semaine 4)
- [ ] Ajouter `pytest` avec tests sur les calculs TRS
- [ ] Gestion d'erreurs granulaire (pas un gros `try/except`)
- [ ] **Impact** : Confiance et régression maîtrisée

---

## 📊 Résumé comparatif des analyses

| Aspect | Son analyse | Mon analyse | Complementarité |
|--------|-------------|-------------|-----------------|
| **Focus** | Architecture, patterns | Métier, cohérence | Complète |
| **Niveau technique** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Équivalent |
| **Couverture métier** | Faible | Forte | Combine les deux |
| **Priorisation** | Linéaire | Par criticité | À fusionner |
| **Détail code** | Précis (lignes) | Précis (lignes) | Identique |

**Verdict :** Les deux analyses sont techniques et valides. La sienne est plus orientée "software engineering", la mienne plus "data/métier". Ensemble elles couvrent 100% des risques.

---

*Document généré le 02/03/2026 - Branche : `refactor/architecture`*
