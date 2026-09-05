# Carte de provenance, segment par segment

*Généré automatiquement par `src/build_dataset.py`.*

Chaque série du jeu de données est un **enchaînement de séries de fournisseurs différents**. Ce document dit, pour chaque mois, quel indice réel est effectivement mesuré.

Les bornes du socle historique ne sont pas reprises d'une documentation : elles ont été **retrouvées dans le fichier lui-même**, en cherchant la plage contiguë sur laquelle le rapport série épissée / composante est constant, puis confirmées par le mois où la composante entrante est rebasée à 100.


## `US` — Actions américaines

| Segment | Début | Fin | Mois | Indice réellement mesuré | Fournisseur | Série source |
|---|---|---|---:|---|---|---|
| `US-1` | 1969-12-31 | 2012-12-31 | 517 | Ibbotson US Large Cap total return | Morningstar / Ibbotson SBBI | Large Caps (col. H) |
| `US-2` | 2013-01-31 | 2016-12-31 | 48 | S&P 500 Total Return | Yahoo Finance | SP500TR (col. G) |
| `US-3` | 2017-01-31 | 2026-07-31 | 115 | S&P 500 Total Return | Yahoo Finance | ^SP500TR |

## `EXUS` — Actions hors États-Unis

| Segment | Début | Fin | Mois | Indice réellement mesuré | Fournisseur | Série source |
|---|---|---|---:|---|---|---|
| `EXUS-1` | 1969-12-31 | 1987-12-31 | 217 | MSCI World ex USA, gross total return, USD | MSCI | WORLD ex USA (col. C) |
| `EXUS-2` | 1988-01-31 | 2016-12-31 | 348 | MSCI ACWI ex USA, gross total return, USD | MSCI | ACWI ex USA (col. D) |
| `EXUS-3` | 2017-01-31 | 2026-07-31 | 115 | MSCI ACWI ex USA via ETF ACWX (net de frais et de retenues) | Yahoo Finance | ACWX, cours ajuste des dividendes |

## `BOND` — Obligations agrégées US

| Segment | Début | Fin | Mois | Indice réellement mesuré | Fournisseur | Série source |
|---|---|---|---:|---|---|---|
| `BOND-1` | 1969-12-31 | 1975-12-31 | 73 | 40% Ibbotson Intermediate Treasuries + 60% Ibbotson Intermediate Corporates, rebalanced monthly | Morningstar / Ibbotson SBBI | Mid-Treasuries + Mid-Corporate (col. J, K) |
| `BOND-2` | 1976-01-31 | 2016-12-31 | 492 | Bloomberg Barclays US Aggregate Bond, total return | Morningstar | AGG (col. F) |
| `BOND-3` | 2017-01-31 | 2026-07-31 | 115 | Bloomberg US Aggregate Bond (via ETF, net de frais) | Yahoo Finance | AGG, cours ajusté des dividendes |

## `TBILL` — Monétaire (T-bills)

| Segment | Début | Fin | Mois | Indice réellement mesuré | Fournisseur | Série source |
|---|---|---|---:|---|---|---|
| `TBILL-1` | 1969-12-31 | 2026-07-31 | 680 | US 1-month Treasury bill | Kenneth French Data Library | F-F_Research_Data_Factors, colonne RF |

## Ce que ces raccords impliquent

- **`EXUS` change d'univers en 1988** : avant, MSCI World ex USA ne couvre que les marchés développés ; après, MSCI ACWI ex USA ajoute les marchés émergents (environ un quart de l'indice aujourd'hui). La série n'est donc pas homogène : la volatilité et la composition géographique changent à cette date. C'est la construction retenue par Antonacci lui-même, et elle reflète ce qu'un investisseur pouvait réellement acheter à chaque époque, mais elle doit être signalée dans le paper.

- **`BOND` change de nature en 1976** : avant, un mélange 40/60 Treasuries/corporates intermédiaires ; après, le Bloomberg Barclays US Aggregate, qui inclut du titrisé et une duration différente. L'indice Aggregate n'existe pas avant janvier 1976 — c'est une limite du monde réel, pas un choix.

- **`US` ne change pas d'indice en 2013**, seulement de fournisseur : la série Ibbotson Large Cap et le S&P 500 Total Return mesurent le même indice. Le raccord est sans effet économique.

- **`TBILL` ne comporte aucun raccord** : une seule source continue de 1926 à aujourd'hui.


## Vérifier les raccords soi-même

`gem_dataset_components.csv` reprend le format du fichier source : **une colonne par série de fournisseur, puis la colonne calculée qui les enchaîne**, plus une colonne `<série>_source` nommant le segment actif ce mois-là.

Chaque composante est remise à l'échelle de la série calculée (changement d'unité seulement, aucun rendement mensuel n'est modifié), si bien qu'en lisant une ligne de gauche à droite la colonne calculée est **exactement égale** à la composante active. Exemple au raccord de 1988 :

```
Date        World ex USA   ACWI ex USA      EXUS   source
1987-12-31       100.000       100.000   100.000   EXUS-1
1988-01-31       101.572       101.680   101.680   EXUS-2   <- bascule
```

Écarts résiduels entre colonne calculée et composante active : nuls sur les segments repris tels quels, et de l'ordre de 1e-5 sur les segments antérieurs à 1988, où le fichier publié n'a que trois décimales. Seule exception, `BOND-1` (3,7e-3) : le mélange 40/60 y est **reconstruit** en composant des rendements mensuels, et l'arrondi du fichier source se cumule sur 73 mois.

La colonne `TBILL_csv_published_not_used` est présente sans être utilisée : elle rend visible la divergence de 2013-2016 qui a motivé l'abandon de cette colonne au profit de Ken French.

