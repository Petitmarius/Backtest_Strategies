# CLAUDE.md

Backtest de la stratégie **Dual Momentum / Global Equities Momentum (GEM)** de
Gary Antonacci, benchmarkée contre le S&P 500.

Objectif final : un **paper de recherche en LaTeX** (graphiques, tables, ratios).
Le code n'est pas une fin en soi — il produit les chiffres et les figures qui
seront cités. La traçabilité des données compte donc autant que la correction du
code.

## Contrainte structurante

**Aucune donnée payante.** Tout doit provenir de sources gratuites et
publiquement accessibles. Cette contrainte est non négociable et a déterminé
toute l'architecture de données. Ne jamais proposer Bloomberg, Global Financial
Data, Refinitiv, ni un abonnement MSCI comme solution — chercher l'alternative
gratuite ou expliciter qu'il n'y en a pas.

## Structure

```
src/data_sources.py      Fetchers bas niveau (une fonction par fournisseur)
src/build_dataset.py     Assemble data/gem_dataset.csv + data/SOURCES.md
src/validate_dataset.py  Audit indépendant -> data/VALIDATION.md
src/gem_backtest.py      Backtest, tables et figures
src/paper_exhibits.py    Exhibits propres au papier (arbre de décision, provenance, annuels)
paper/gem.tex            Manuscrit LaTeX
paper/references.bib     Bibliographie, chaque entrée vérifiée à la source
paper/OUTLINE.md         Plan arrêté du papier

data/gem_dataset.csv          Jeu maître FORMAT LARGE, 4 séries — entrée du backtest (généré)
data/gem_dataset_detailed.csv Format long, une ligne par (date, série) avec sa provenance (généré)
data/gem_dataset_components.csv Format large : composantes brutes + colonne calculée (généré)
data/gem_dataset.manifest.json Empreinte SHA-256 + statistiques, pour --verify (généré)
data/README.md                Mode d'emploi du dataset pour un tiers
data/cache/                   Copies disque des sources live, filet de sécurité (non versionné)
data/SEGMENTS.md              Carte de provenance segment par segment (généré)
data/SOURCES.md               Provenance globale, à citer dans le paper (généré)
data/VALIDATION.md            Rapport d'audit des données (généré)
output/figures/          PNG (généré)
output/tables/           CSV (généré)
```

Les fichiers marqués « généré » ne se modifient **jamais** à la main : il faut
changer le script qui les produit et le relancer.

## Commandes

```bash
python src/build_dataset.py             # --verify (défaut) : contrôle hors ligne
python src/build_dataset.py --refresh   # ajoute UNIQUEMENT les mois nouveaux
python src/build_dataset.py --rebuild --force   # tout refaire (geste délibéré)
python src/validate_dataset.py          # régénère l'audit (réseau, ~2 min)
python src/gem_backtest.py              # backtest + figures + tables (hors ligne)
python src/paper_exhibits.py            # exhibits du papier (hors ligne)
python src/make_tables.py               # tableaux LaTeX depuis les CSV calculés
python src/check_paper_numbers.py       # contrôle les chiffres du texte
tectonic -X compile paper/gem.tex       # compile le manuscrit
```

**Aucun chiffre du papier n'est saisi à la main dans un tableau ou une figure**
— ils sont générés. Le texte, lui, est écrit à la main et peut donc dériver :
`check_paper_numbers.py` recalcule chaque chiffre affirmé dans la prose et sort
en erreur si l'un ne correspond plus. À lancer après toute reconstruction du
dataset. Il a déjà attrapé deux dérives réelles.

**Tectonic** est installé dans `~/AppData/Local/Programs/tectonic/` : un binaire
unique qui télécharge ses paquets à la demande, aucune distribution LaTeX
complète nécessaire.

**Ne jamais écrire un `.tex` avec un heredoc bash** : même avec un délimiteur
entre quotes, `\` y est réduit à `\`, ce qui casse silencieusement les fins de
ligne des tableaux. Utiliser l'outil Write.

**Le dataset est un artefact gelé, pas une sortie de build.** `--refresh`
recopie verbatim les mois déjà publiés et n'ajoute que les nouveaux ; si une
source renvoie une valeur différente pour un mois publié (au-delà de 1e-5 en
relatif), il refuse d'écrire et affiche les écarts. Ne jamais utiliser
`--rebuild --force` pour contourner ce refus sans avoir compris la cause.

`gem_backtest.py` lit uniquement le CSV : il tourne sans réseau et de façon
déterministe.

## Données

Quatre séries de **niveaux d'indices en rendement total, en USD, mensuelles**,
de 1969-12 à aujourd'hui :

| Colonne | Contenu |
|---|---|
| `US` | Actions américaines (Ibbotson Large Cap → S&P 500 TR) |
| `EXUS` | Actions hors US (MSCI World ex USA → MSCI ACWI ex USA, gross) |
| `BOND` | Obligations agrégées US (Ibbotson gov/corp → Bloomberg Barclays US Agg) |
| `TBILL` | T-bills 1 mois (Ken French, source unique continue depuis 1926) |

**Trois fichiers, trois usages.** `gem_dataset.csv` est l'entrée du code : schéma
large stable, 4 colonnes, rien d'autre. `gem_dataset_detailed.csv` est la version
documentaire : format long, avec pour chaque mois l'indice réellement mesuré, le
fournisseur, le segment et un drapeau `repaired`. `gem_dataset_components.csv`
reprend le format du fichier source : une colonne par série de fournisseur, puis
la colonne calculée qui les enchaîne, chaque composante étant remise à l'échelle
de la série calculée pour que la bascule se vérifie à l'œil sur une ligne. Ne
jamais faire lire l'un de ces deux fichiers au backtest — leur schéma change à
chaque ajout de métadonnée.

Si une source live est indisponible, `cached()` retombe sur `data/cache/`. Sans
ce filet, un simple timeout laisserait une colonne courte et le `dropna()` final
tronquerait **tout** le dataset à 2016 — un incident réseau se transformerait en
dix ans de données manquantes.

Les bornes de raccord de `SEGMENTS.md` ne sont pas reprises d'une documentation :
elles sont **retrouvées dans le fichier source** par recherche de la plage où le
rapport série épissée / composante est constant. Les noms de colonnes du CSV sont
des références de cellules de tableur (`Spliced C and D` = colonne C puis D), ce
qui rend la recette vérifiable.

Socle historique jusqu'à 2016-12 : `msci_all_gross.csv` du dépôt
[alexjansenhome/GEM](https://github.com/alexjansenhome/GEM). C'est une
**redistribution, pas une source primaire** — d'où l'audit systématique. Le
prolongement jusqu'à aujourd'hui vient de Yahoo, de l'API publique MSCI et de la
Ken French Data Library.

### Défaut connu du fichier source

Trois observations de novembre (1990, 1991, 1992) de la colonne T-bills ont
**perdu leur chiffre de tête** (`0.366` au lieu de `10.366`). Non corrigé, ce
défaut injecte un rendement mensuel de −96 % puis +2 749 % et fausse le signal de
momentum absolu sur 1990-1993. Corrigé dans `repair_monotone_index()`, en
exploitant le fait qu'un indice monétaire ne peut jamais baisser. Après
correction, la corrélation avec le T-bill de Ken French passe de 0,025 à 0,994.

**Ne jamais désactiver cette correction** sans relancer `validate_dataset.py`.

Deuxième défaut, contourné plutôt que corrigé : sur 2013-2016 la colonne T-bills
du CSV implique 0,95 %/an alors que le vrai taux était de 0,06 %. La colonne est
donc abandonnée au profit de Ken French sur toute la période — les deux coïncident
à 0,00 point près sur 1970-2012, et French est juste là où le CSV se trompe. Cela
supprime un raccord et un défaut d'un coup. Impact mesuré sur les décisions GEM :
**zéro mois sur 667**.

Troisième piège, silencieux : à partir de mi-1986 les colonnes `USA` et
`WORLD ex USA` dépassent 1000 et sont écrites `"1,079.18"`. Sans `thousands=","`
elles se lisent comme du texte, `pd.to_numeric` les transforme en NaN et 293 et
365 observations disparaissent sans la moindre erreur. Les 4 colonnes de
production ne sont pas touchées, mais le fichier détaillé les utilise.

## Pièges réseau (vérifiés empiriquement, pas documentés ailleurs)

- **`yfinance` avec `interval="1mo"` tronque silencieusement l'historique** vers
  1985. `^GSPC` renvoie 1985+ en mensuel mais 1927+ en journalier. Toujours
  télécharger en `interval="1d"` puis rééchantillonner.
- **L'API MSCI tronque le début des séries** sur les fenêtres larges : demander
  1997-2026 en un appel renvoie à partir de 2000. Paginer par tranches de 3 ans.
  Plancher dur à 1997-01-01. Header `Referer` obligatoire.
- **FRED se bloque sans en-tête `Accept`**, et se bloque aussi avec un
  User-Agent Chrome complet. Il répond en ~0,1 s avec `PLAIN_UA`. Dans les deux
  cas la connexion est acceptée puis jamais servie : ça ressemble à une panne
  réseau, pas à un refus.
- Stooq (challenge JS) et Investing.com (403) sont inutilisables en script.
- **L'API MSCI throttle et renvoie alors 200 avec des pages manquantes**, pas une
  erreur. `_exus_live()` détecte les trous et bascule sur l'ETF ACWX ; `cached()`
  rebouche depuis le disque ; `splice()` **refuse** un raccord troué au lieu de
  reculer la jonction. Sans ces trois garde-fous un simple throttling produisait
  un dataset de 632 mois au lieu de 680, sans le moindre message.

## Conventions

- **Pas de look-ahead.** Le signal est calculé sur le mois `t-1` et la position
  encaisse le rendement du mois `t`. Toute modification de `run_rule()` doit
  préserver cette règle.
- **Sources gratuites uniquement**, et chaque nouvelle source s'ajoute à
  `data_sources.py`, jamais en ligne dans un script d'analyse.
- **Statistiques en numpy pur.** `scipy` et `statsmodels` ne sont pas installés
  et on ne les ajoute pas : les erreurs-types Newey-West sont implémentées à la
  main dans `gem_backtest.py`. Les rendements mensuels d'une règle de momentum
  sont autocorrélés, donc un t-test naïf surestime la significativité.
- **Conversation avec l'utilisateur en français.** Code, noms de variables,
  docstrings et commentaires en anglais.
- **Tout ce qui atterrit dans le papier est en anglais** : libellés de figures,
  titres, annotations, en-têtes de tableaux, noms de séries. Le papier est en
  anglais ; une figure en français dedans est une erreur. La sortie console des
  scripts suit la même langue, par cohérence avec le code.
- Figures : matplotlib seul, palette de `COLORS`, lisible en niveaux de gris,
  export simultané en PNG (relecture) et PDF vectoriel (LaTeX).

## Résultats de référence (1971-01 → 2026-07)

À utiliser comme test de non-régression : un changement qui déplace ces chiffres
de plus de ~0,1 point doit être expliqué.

| | CAGR | Vol | Sharpe | MaxDD |
|---|---:|---:|---:|---:|
| GEM | 15,18 % | 12,91 % | 0,83 | −21,66 % |
| S&P 500 | 11,27 % | 15,20 % | 0,50 | −50,95 % |

Alpha annualisé 6,61 % (t = 4,31 Newey-West), bêta 0,57, R² 0,45.
Décomposition d'Antonacci : momentum absolu seul +77 bps, relatif seul +203 bps,
combiné +391 bps — les deux briques ne s'additionnent pas, ce qui est le point
central de l'article original.

Effet allocation contre effet timing (table 2b) : le mix statique portant la même
allocation moyenne que GEM (46/28/25, figé, rebalancé mensuellement) fait 10,03 %,
soit **124 bps de MOINS que le S&P 500**. Le panier d'actifs est donc un handicap
sur la période — hors US et obligations ont sous-performé les actions US. La
totalité des +391 bps vient du timing, qui doit d'abord effacer ce handicap
(+515 bps bruts). Le drawdown, lui, se partage : −9,0 pt dus à l'allocation,
−20,3 pt de plus dus au timing.

Fait le plus important du backtest : toute la surperformance vient de 1971-2009
(+7,7 pt/an). Sur 2010-2026 GEM perd 4,8 pt/an. La cause est mesurée : sur cette
période la règle n'est hors du S&P 500 que 26 % du temps, mais pendant les 21
mois passés en obligations le S&P 500 progressait de +34 %/an annualisé — contre
+5,3 %/an pendant les 149 mois défensifs de 1971-2009. Le signal défensif est
devenu un signal de sortie au plus bas.

## Références

- Antonacci, *Extended Backtest of Global Equities Momentum* (1950-2018).
- Grzegorz Link, *Dual Momentum and Global Growth Cycle Enhanced* (1970-2025) —
  <https://grzegorz.link/momentum-enhanced>.
- `SSRN_Dual_Momentum.pdf` à la racine (Antonacci, 2016).
