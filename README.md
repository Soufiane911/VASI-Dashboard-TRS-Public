## OutilTRS - Système d'Audit et d'Analyse du Rendement Synthétique

Application web d'audit du TRS (Taux de Rendement Synthétique) pour analyser et comparer la capacité réelle de production aux données déclarées par le système ERP.

---

## 1. Contexte et Problématique

### 1.1 Enjeu Identifié

Les systèmes de planification ERP (Enterprise Resource Planning) tendent à surestimer la capacité de production disponible. Cette surestimation résulte d'une méthodologie de calcul qui exclut les périodes d'inactivité du calcul du TRS global, créant ainsi un écart significatif entre la capacité déclarée et la capacité réelle observable.

### 1.2 Impact Opérationnel

Cette divergence entraine :
- Une planification irréaliste des calendriers de production
- Des promesses de délai de livraison non respectées
- Une désorganisation du flux de production
- Une perte de confiance clients

### 1.3 Analyse Comparative

L'ERP applique une méthodologie d'exclusion des zéros : seules les lignes de production avec activité sont intégrées au calcul du TRS moyen.

La norme NF E60-182 impose une méthodologie inclusive : la capacité réelle rapporte le temps utile à l'ensemble du temps disponible, y compris les périodes sans production.

---

## 2. Approche Méthodologique

### 2.1 Norme de Référence

OutilTRS implémente le calcul du TRS selon la norme française NF E60-182:2016 "Méthode de calcul de la disponibilité, de la performance et de la qualité".

### 2.2 Architecture de Calcul

Le TRS est décomposé en trois composantes multiplicatives :

```
TRS = Do × Tp × Tq
```

où :

- **Do (Disponibilité)** = Temps de fonctionnement réel / Temps requis disponible
  - Mesure les arrêts machines (pannes, changements d'outils, etc.)
  - Rapport : heures de production / heures de capacité

- **Tp (Performance)** = Temps net / Temps de fonctionnement réel
  - Mesure la vitesse réelle vs. vitesse théorique
  - Calcul : (Nombre de cycles × Cycle théorique) / Temps de fonctionnement

- **Tq (Qualité)** = Pièces conformes / Pièces produites
  - Mesure le taux de conformité
  - Inclut les rebuts et retouches

### 2.3 Implémentation Ligne par Ligne

Chaque ligne de données ERP est traitée individuellement selon les formules NF E60-182 :

```
Disponibilité : Do(i) = Tps_Fct_Brut(i) / Tps_Requis(i)
Performance : Tp(i) = (Nb_Cycles(i) × Cycle_Theo(i)) / (3600 × Tps_Fct_Brut(i))
Qualité : Tq(i) = Pieces_Bonnes(i) / Pieces_Fab(i)
TRS(i) = Do(i) × Tp(i) × Tq(i)
```

### 2.4 Agrégation Globale

Contrairement au calcul ligne par ligne, l'audit TRS global utilise une agrégation par temps :

```
TRS_Réel = Sigma(Tps_Utile) / Sigma(Tps_Disponible)

où :
- Sigma(Tps_Utile) = somme des temps utiles sur toutes les lignes
- Sigma(Tps_Disponible) = somme des temps disponibles sur toutes les lignes
```

Cette approche garantit que les périodes sans production sont incluses dans le dénominateur.

---

## 3. Détection des Anomalies

L'application détecte automatiquement les incohérences dans les données ERP brutes :

- TRS ERP > 100% ou < 0% (valeur impossible)
- Taux de performance > 100% (performance supérieure au théorique)
- Taux de qualité > 100% (impossible mathématiquement)
- Pièces bonnes négatives (erreur de saisie)
- Rebuts supérieurs à la production totale (incohérence)

Ces anomalies signalent des erreurs de saisie ou de configuration ERP.

---

## 4. Fonctionnalités Principales

### 4.1 Import de Données

Accepte les fichiers d'export ERP aux formats :
- XLSX avec feuille "RESULTAT_EQUIPE"
- CSV avec délimiteur point-virgule (;)

Traitement automatique :
- Saut des 10 premières lignes (métadonnées ERP)
- Suppression des lignes de totaux
- Dédoublonnage des enregistrements
- Création de périodes mensuelles

### 4.2 Filtrage Dynamique

Les données peuvent être filtrées selon :
- Période mensuelle
- Référence machine / presse
- Référence outillage
- Référence produit
- Critères d'anomalies et TRS = 0

Les KPI sont recalculés en temps réel selon les filtres appliqués.

### 4.3 Extraction de KPI

Calcul et affichage des indicateurs clés :
- TRS ERP (valeur déclarée)
- TRS Réel (capacité réelle)
- Écart en points et pourcentage
- Composantes Do, Tp, Tq pour ERP et réel
- Statistiques de conformité

### 4.4 Visualisations

- Jauges circulaires (ring gauge) pour les composantes Do, Tp, Tq
- Graphique d'évolution TRS par mois
- Tableau synthétique mensuel

### 4.5 Export de Rapport

Génération d'un fichier Excel contenant :
- Onglet Audit_TRS : résumé exécutif avec écarts
- Onglet Données_Audit : dataset complet avec colonnes calculées
- Onglet Alertes : lignes identifiées comme anomalies

---

## 5. Installation et Utilisation

### 5.1 Configuration Locale

Prérequis : Python 3.8 ou supérieur

```bash
cd OutilTRS-Streamlit
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

L'application démarre sur http://localhost:8501

### 5.2 Déploiement Cloud

Streamlit Community Cloud (gratuit) :

1. Initialiser le repository GitHub
2. Pousser le code vers le repository
3. Accéder à https://share.streamlit.io
4. Sélectionner le repository et le fichier streamlit_app.py
5. Déploiement automatique

Une URL publique est générée pour l'accès web.

---

## 6. Architecture Technique

### 6.1 Structure Modulaire

```
streamlit_app.py        Interface utilisateur et orchestration
├─ parser.py           Extraction et nettoyage des données ERP
├─ calculator.py       Calcul TRS selon NF E60-182
├─ filters.py          Filtrage et agrégation des KPI
└─ exporter.py         Génération rapports Excel
```

### 6.2 Flux de Traitement

```
Fichier ERP (XLSX/CSV)
    |
    v
parser.py
    - Lecture des feuilles
    - Nettoyage métadonnées
    - Suppression lignes totaux
    |
    v
calculator.py
    - Conversion pourcentages texte
    - Calcul composantes Do, Tp, Tq
    - Calcul TRS ligne par ligne
    - Détection anomalies
    |
    v
filters.py
    - Filtrage selon critères
    - Agrégation KPI
    - Groupement mensuel
    |
    v
Affichage Streamlit
    - KPI circulaires
    - Graphiques Plotly
    - Tableaux pandas
    - Filtres interactifs
    |
    v
exporter.py
    - Export Excel multi-onglets
```

### 6.3 Dépendances

| Paquet | Version | Utilisation |
|--------|---------|-------------|
| streamlit | ≥1.30.0 | Framework web |
| pandas | ≥2.0.0 | Traitement données tabulaires |
| plotly | ≥5.18.0 | Graphiques interactifs |
| openpyxl | ≥3.1.0 | Lecture fichiers XLSX |
| xlsxwriter | ≥3.1.0 | Écriture fichiers XLSX |

---

## 7. Validation et Limites

### 7.1 Hypothèses

- Les colonnes ERP requises sont présentes dans l'export
- Les valeurs numériques sont correctement formatées dans l'ERP
- Les périodes mensuelles peuvent être extraites de la colonne "Début Equipe"
- Cycle théorique constant pour une même référence de produit

### 7.2 Limitations Observées

- Les fichiers uploadés ne sont pas persistants (Streamlit Cloud)
- Performance dépendante de la taille du dataset (optimal < 100k lignes)
- Pas de support pour historique multi-années
- Nécessite accès direct aux exports ERP (pas d'API)

### 7.3 Critères de Qualité des Données

L'application requiert pour chaque ligne :
- Réf OF non vide
- Tps Fct Brut (h) >= 0
- Nb Cycles et Cycle Théo numériques
- Qté Pieces Fab et Qté Pieces Bonnes cohérentes

Les lignes non conformes sont signalées comme anomalies.

---

## 8. Cas d'Usage

### 8.1 Validation Planification

Vérification de la capacité réelle vs. promesses commerciales :
- Import export ERP
- Calcul TRS réel
- Comparaison avec TRS déclaré
- Réajustement calendrier commercial si écart > 15%

### 8.2 Diagnostic Goulot d'Étranglement

Identification des facteurs limitants :
- Do faible : problèmes de disponibilité machine
- Tp faible : vitesse réelle < vitesse théorique
- Tq faible : taux de rebuts élevé

Action : prioriser amélioration selon composante faible.

### 8.3 Audit Qualité Données ERP

Détection anomalies saisie :
- Signalement automatique valeurs hors limites
- Export liste anomalies pour correction ERP
- Validation avant réutilisation données de planification

---

## 9. Interprétation des Résultats

### 9.1 Exemple Numérique

Cas réel observé :
- TRS ERP : 54% (moyenne, excluant zéros)
- TRS Réel : 28% (global, incluant tout)
- Écart : 26 points (92% surestimation)

Interprétation :
L'ERP planifie sur une base de 54% disponibilité, tandis que la réalité observable est 28%. Cet écart de 26 points signifie que la planification surpromet une capacité 1.93x supérieure à la réalité.

### 9.2 Dégradation Acceptable

Seuils empiriques :
- Écart 0-10% : acceptable, variabilité normale
- Écart 10-20% : attention requise
- Écart > 20% : dysfonctionnement systémique

---

## 10. Maintenance et Évolutions

### 10.1 Dépannage

Erreur "Pas de donnée valide" :
- Vérifier présence colonne "Début Equipe"
- Vérifier présence feuille "RESULTAT_EQUIPE" (XLSX)
- Valider format CSV avec séparateur ;

Erreur "Colonne manquante" :
- Vérifier structure export ERP
- Vérifier colonnes : Réf OF, Tps Fct Brut (h), Nb Cycles, Qté Pieces Fab, T.R.S.

Performance dégradée :
- Limiter à < 100k lignes par import
- Filtrer par mois plutôt que chargement global

### 10.2 Versionning

Format : OutilTRS vX.Y.Z

Historique stocké dans les métadonnées de commits Git.

---

## 11. Documentation Références

- NF E60-182:2016 - Disponibilité, performance et qualité en production
- Norme ISO 9000 - Gestion de la qualité
- ERP Documentation - Export RESULTAT_EQUIPE format

---

## 12. Informations Projet

Auteur : Équipe Stage VASI
Date de création : Janvier 2026
Norme applicable : NF E60-182:2016
Classification : Interne VASI
Support : Contact administrateur système

---

## Licence et Confidentialité

Usage interne VASI exclusivement. Toute distribution externe requiert approbation direction.
