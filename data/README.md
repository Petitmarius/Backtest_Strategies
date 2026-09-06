# Jeu de données GEM — 1969-12 à 2026-07

Quatre séries mensuelles de **niveaux d'indices en rendement total, en USD**,
construites uniquement à partir de sources gratuites.

**Le dataset est gelé.** Ce n'est pas une sortie de build qu'il faut régénérer :
c'est un artefact versionné, avec son empreinte. Vous pouvez l'utiliser tel quel,
sans réseau, sans clé d'API, sans rien reconstruire.

## Utiliser le dataset

```python
import pandas as pd
px = pd.read_csv("data/gem_dataset.csv", index_col="Date", parse_dates=True)
```

| Colonne | Contenu |
|---|---|
| `US` | Actions américaines |
| `EXUS` | Actions hors États-Unis |
| `BOND` | Obligations agrégées US |
| `TBILL` | Bons du Trésor 1 mois |

Ce sont des **niveaux d'indices**, pas des rendements : `px.pct_change()` donne
les rendements mensuels. Les niveaux n'ont pas de sens en valeur absolue (chaque
fournisseur a sa propre base), seuls leurs mouvements en ont.

## Les quatre fichiers

| Fichier | Pour quoi faire |
|---|---|
| `gem_dataset.csv` | **Le dataset.** Format large, 4 colonnes. C'est ce que lit le backtest. |
| `gem_dataset_components.csv` | Chaque série de fournisseur en regard de la colonne calculée, pour vérifier les raccords à l'œil. |
| `gem_dataset_detailed.csv` | Format long : une ligne par (date, série), avec sa provenance. |
| `gem_dataset.manifest.json` | Empreinte SHA-256, nombre de lignes, période, CAGR et volatilité par colonne. |

Et trois documents : [`SEGMENTS.md`](SEGMENTS.md) (quel indice est mesuré à quelle
période), [`SOURCES.md`](SOURCES.md) (provenance) et
[`VALIDATION.md`](VALIDATION.md) (l'audit).

## Vérifier qu'il est intact

```bash
python src/build_dataset.py          # --verify est le mode par défaut
```

Contrôle hors ligne du fichier contre son manifeste : hash, nombre de lignes, et
CAGR de chaque colonne. N'écrit rien, n'appelle rien. C'est ce qui rend les
chiffres du papier vérifiables par un tiers.

## Le mettre à jour

```bash
python src/build_dataset.py --refresh
```

**Ajoute uniquement les mois nouveaux.** Les mois déjà publiés sont recopiés
verbatim depuis le fichier existant, jamais recalculés. Si une source venait à
renvoyer des valeurs différentes pour un mois déjà publié, le script **refuse
d'écrire** et affiche le détail des écarts.

Tout reconstruire depuis zéro demande un geste explicite :

```bash
python src/build_dataset.py --rebuild --force
```

À n'utiliser que si un changement de l'historique est voulu et documenté — par
exemple un fournisseur ayant révisé sa série.

## Ce qu'il faut savoir avant de s'en servir

**Les séries changent d'indice au fil du temps.** `EXUS` mesure le MSCI World ex
USA jusqu'en 1987 puis le MSCI ACWI ex USA à partir de 1988 : l'univers change,
les émergents entrent. `BOND` est un mélange Ibbotson jusqu'en 1975 puis le
Bloomberg Barclays US Aggregate, qui n'existe pas avant janvier 1976. Ces
raccords ne sont pas des approximations de confort, ils reflètent ce qui existait
réellement à chaque époque — mais ils doivent être signalés dans tout travail
publié. Le détail est dans [`SEGMENTS.md`](SEGMENTS.md).

**Le socle historique est une redistribution, pas une source primaire.** Il vient
du fichier `msci_all_gross.csv` du dépôt
[alexjansenhome/GEM](https://github.com/alexjansenhome/GEM), qui reproduit la
construction d'Antonacci. C'est pourquoi il est confronté à neuf références
indépendantes dans [`VALIDATION.md`](VALIDATION.md) — un audit qui a d'ailleurs
trouvé un vrai défaut, corrigé depuis.

**Aucune donnée payante.** Tout provient de Yahoo Finance, de l'API publique
MSCI et de la Kenneth French Data Library.
