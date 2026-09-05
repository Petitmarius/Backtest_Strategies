# Dual Momentum (GEM) — backtest sur données gratuites

Réplication du **Global Equities Momentum** de Gary Antonacci, 1971-2026,
construite exclusivement à partir de sources de données **gratuites**.

## Règle

Chaque mois, avec la seule information disponible à cette date :

```
si  rendement 12 mois(actions US) > rendement 12 mois(T-bills):   # momentum absolu
        détenir US ou hors-US, selon le meilleur rendement 12 mois # momentum relatif
sinon:
        détenir des obligations agrégées US
```

## Résultats (1971-01 → 2026-07, 667 mois)

| | CAGR | Volatilité | Sharpe | Max drawdown |
|---|---:|---:|---:|---:|
| **GEM** | **15,18 %** | 12,91 % | **0,83** | **−21,66 %** |
| S&P 500 | 11,27 % | 15,20 % | 0,50 | −50,95 % |

Alpha annualisé 6,61 % (t = 4,31, erreurs-types Newey-West), bêta 0,57, R² 0,45.

**Décomposition** — les deux briques ne s'additionnent pas : momentum absolu seul
+77 bps, relatif seul +203 bps, combiné **+391 bps**.

**Allocation contre timing** : un portefeuille statique portant la même allocation
moyenne que GEM (46 % US / 28 % hors US / 25 % obligations, rebalancé chaque mois)
rend 10,03 % — soit 124 bps de *moins* que le S&P 500. Le panier d'actifs est donc
un handicap sur la période ; l'intégralité de la surperformance vient du timing.

**Réserve principale** : toute la surperformance vient de 1971-2009 (+7,7 pt/an).
Sur 2010-2026 GEM perd 4,8 pt/an face au S&P 500.

## Données

Quatre séries mensuelles de niveaux en rendement total, USD, depuis 1969-12.
Socle historique issu d'un CSV redistribué, prolongé par Yahoo Finance, l'API
publique MSCI et la Kenneth French Data Library.

Ce socle est une redistribution, pas une source primaire : il est donc **audité
contre neuf références indépendantes**, et l'audit a trouvé un défaut réel (trois
observations de T-bills ayant perdu leur chiffre de tête, corrigées). Voir
[`data/VALIDATION.md`](data/VALIDATION.md) et [`data/SEGMENTS.md`](data/SEGMENTS.md).

## Utilisation

```bash
pip install -r requirements.txt
python src/build_dataset.py       # reconstruit le jeu de données (réseau)
python src/validate_dataset.py    # régénère l'audit (réseau)
python src/gem_backtest.py        # backtest, figures et tables (hors ligne)
```

## Structure

| Chemin | Rôle |
|---|---|
| `src/data_sources.py` | Fetchers, un par fournisseur |
| `src/build_dataset.py` | Assemblage du jeu de données et de sa provenance |
| `src/validate_dataset.py` | Audit indépendant des données |
| `src/gem_backtest.py` | Backtest, statistiques, figures |
| `data/` | Jeu de données et documentation de provenance |
| `output/` | Figures et tables générées |
