# Provenance des données

*Généré automatiquement par `src/build_dataset.py`.*

Jeu de données : `data/gem_dataset.csv` — **1969-12-31 → 2026-07-31**, 680 observations mensuelles, niveaux d'indices en rendement total, USD.


## Socle historique (1969-12-31 → 2016-12-31)

Fichier `msci_all_gross.csv` du dépôt [alexjansenhome/GEM](https://github.com/alexjansenhome/GEM), qui reproduit la construction d'Antonacci.

URL exacte : `https://raw.githubusercontent.com/alexjansenhome/GEM/master/msci_all_gross.csv`

| Clé | Colonne d'origine | Contenu |
|---|---|---|
| `US` | `Spliced H+G` | Ibbotson US Large Cap TR spliced to S&P 500 Total Return (Yahoo) |
| `EXUS` | `Spliced C and D` | MSCI World ex USA gross TR spliced to MSCI ACWI ex USA gross TR |
| `BOND` | `Spliced F+40%J+60%K` | 40% Ibbotson Intermediate Treasuries + 60% Ibbotson Intermediate Corporates, spliced to Bloomberg Barclays US Aggregate TR |
| `TBILL` | `Spliced M+R` | Ibbotson 30-day T-bills spliced to FRED 4-week T-bill |

Ce fichier est une **redistribution**, pas une source primaire. Il est audité contre neuf références indépendantes dans [`VALIDATION.md`](VALIDATION.md).


### Correction appliquée

3 observation(s) de la jambe monétaire avaient perdu leur chiffre de tête dans le fichier publié. Corrigées par moyenne géométrique des mois voisins :

| Mois | Publié | Retenu |
|---|---:|---:|
| 1990-11-30 | 0.366 | 10.368 |
| 1991-11-30 | 0.970 | 10.970 |
| 1992-11-30 | 1.366 | 11.369 |

## Prolongement (2016-12-31 → 2026-07-31)

| Clé | Source | Raccord | Facteur d'échelle | Mois ajoutés |
|---|---|---|---:|---:|
| `US` | Yahoo Finance, ^SP500TR (S&P 500 Total Return index) | 2016-12-31 | 1.000000 | 117 |
| `EXUS` | MSCI public API, index 664211 (repli ETF ACWX) | 2016-12-31 | 0.471889 | 116 |
| `BOND` | Yahoo Finance, AGG (iShares Core US Aggregate Bond ETF) | 2016-12-31 | 24.131483 | 117 |

Le raccord est un **changement de base uniquement** : la série live est multipliée par une constante pour coïncider avec le socle au mois de jonction. Aucun rendement mensuel n'est modifié, ni avant ni après le raccord.


## Reproduire

```bash
python src/build_dataset.py     # reconstruit data/gem_dataset.csv
python src/validate_dataset.py  # régénère data/VALIDATION.md
```

