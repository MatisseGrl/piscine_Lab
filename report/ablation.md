# Rapport d'ablation

2 pages maximum. Même modèle, même budget, seules les données changent.

> Trame préparée le 10/11/2026. Les cases « à mesurer » attendent les runs Kaggle. Aucun chiffre de BPB n'est inventé.

## Protocole

- **Modèle et entraînement :** configuration figée du kit (`config/official.json`, kit à `3709c85`), graine 1337, 3 052 pas, soit 100 007 936 tokens vus par run, une seule passe sur les données. Entraînement sur Kaggle T4.
- **Tokenizer :** un seul, de 8 192 entrées, appris sur 10 Mo du nettoyé avec le mélange validé. Le même fichier sert à toutes les variantes (SHA-256 `b2554a82…2379`). Limite : appris sur le nettoyé, ce qui peut l'avantager.
- **Mélange :** 80 % Wikipédia FR, 12 % Common Crawl, 8 % Assemblée nationale, **compté en tokens**, mêmes proportions dans chaque fenêtre de mélange, graine 42 pour les tirages.
- **Validation :** les 230 documents publics du kit. BPB = bits de NLL divisés par les **octets UTF-8** (813 051). Aucune suite de 13 mots en commun avec l'entraînement, vérifiée sur chaque variante.

## Variantes comparées

| Variante | Étapes appliquées | Documents | Octets UTF-8 |
|---|---|---:|---:|
| Brut contrôlé | collecte + export brut | voir `clean/stats.json` | |
| Nettoyé | encodage, langue (fastText ≥ 0,80), boilerplate | 2 530 051 | 7 795 353 284 |
| Dédupliqué | + exact + MinHash (Jaccard 0,97), Wikipédia plafonné à 300 000 articles | 320 319 | 1 056 674 469 |
| + qualité | + lettres ≥ 30 %, Common Crawl : ≥ 100 car., lignes répétées ≤ 60 % | 320 098 | 1 053 824 598 |
| + PII | + masquage regex (e-mail, téléphone, IBAN, URL, IP) | 320 319 | 1 055 854 450 |
| + qualité + PII | les deux | 320 098 | 1 053 018 328 |

## Résultats

| Données | Tokens vus | BPB val | Écart vs référence |
|---|---|---|---|
| Brutes | 100 007 936 | à mesurer | référence |
| Nettoyées | 100 007 936 | à mesurer | vs brutes |
| Dédupliquées | 100 007 936 | à mesurer | vs nettoyées |
| + qualité | 100 007 936 | à mesurer | vs dédupliquées |
| + PII | 100 007 936 | à mesurer | vs dédupliquées |
| + qualité + PII | 100 007 936 | à mesurer | vs dédupliquées |

## Quelles étapes ont le plus d'impact ?

À remplir avec les BPB. Ce que le pipeline mesure déjà : le nettoyage rejette 96 % des pages Common Crawl, la déduplication retire peu de documents sur le nettoyé (3 815 doublons exacts puis 199 par MinHash), la qualité retire 0,07 % des documents.

## Lesquelles ne servent à rien ?

Hypothèse à confirmer ou infirmer par la mesure : le filtre qualité, vu son taux de rejet, et le masquage PII, qui change environ 0,1 % des octets. Une étape qui ne baisse pas le BPB à configuration identique est à dire sans détour.

## Échecs et surprises

À compléter. Limites déjà connues : le contraste nettoyé → dédupliqué inclut le plafonnement de Wikipédia ; le tokenizer est appris sur le nettoyé ; une seule graine d'entraînement, donc pas de barre d'erreur ; le masquage ne détecte ni noms ni adresses postales.

## Ablation des sources (mélanges M1 à M5, 14-15/11)

Même protocole : kit `3709c85`, config officielle, tokenizer 8 192 commun, 100 007 936 tokens vus, micro-batch 8, GPU T4 (Colab ou Kaggle), validation publique de 230 documents. Toutes les sources passent par dédup + qualité, sans PII. Deux sources ajoutées : Gutenberg FR (PR #32) et Wikinews FR (PR #31). Construction : `pipeline/mixes.py`. Fichiers bruts : `Kaggle submissions/mixes/<ID>/`.

**Bruit** (`report/noise.md`) : la référence 80/12/8 donne 1,3304 / 1,3315 / 1,3270, moyenne **1,3296**, σ 0,0023. Une amélioration ne compte que si elle dépasse **~0,005**. Contrôles ajoutés : M3 relancé à l'identique sur un autre GPU (1,3151 puis 1,3146, écart 0,0005) et M4 avec une 2e graine (1,3028 puis 1,3066).

| Mélange (tokens) | Wiki | CC | AN | Gut. | WN | BPB | Écart vs 1,3296 | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Référence 80/12/8 | 80 | 12 | 8 | – | – | 1,3296 (moy. 3) | – | référence |
| M1 | 35 | 15 | 20 | 30 | – | 1,3262 | −0,0034 | pas de différence démontrée |
| M2 | 25 | 25 | 25 | 25 | – | 1,3469 | +0,0173 | dégradation |
| M3 | 50 | 15 | 10 | 25 | – | 1,3151 / 1,3146 | −0,015 | gain (1 graine, 2 GPU) |
| **M4** | 40 | 15 | 15 | 25 | 5 | **1,3028 / 1,3066** (moy. 1,3047) | **−0,025** | **gain confirmé sur 2 graines** |
| M5 | 60 | 12 | 8 | 20 | – | 1,3138 | −0,016 | gain (1 graine) |

Par genre (BPB ; référence = moyenne du bruit) :

| Genre | Réf. | M1 | M2 | M3 | M4 (g. 1337) | M5 |
|---|---:|---:|---:|---:|---:|---:|
| Littéraire | 1,673 | 1,576 | 1,646 | 1,558 | 1,547 | 1,557 |
| Dialogue | 1,127 | 1,084 | 1,076 | 1,110 | 1,092 | 1,120 |
| Encyclopédique | 1,311 | 1,395 | 1,419 | 1,357 | 1,373 | 1,345 |
| Presse | 1,206 | 1,252 | 1,248 | 1,236 | 1,200 | 1,234 |

**Ce que ça montre**
- **Gutenberg est la source qui compte** : 20 à 30 % de livres font baisser le littéraire d'environ 0,10 à 0,13 dans tous les mélanges. C'est l'essentiel du gain global.
- **Baisser Wikipédia coûte en encyclopédique** (+0,03 à +0,11), de façon à peu près proportionnelle. M2 (25 %) est le pire.
- **M4 est le seul mélange qui ne perd pas en presse** (1,200, soit −0,006, dans le bruit), sans doute grâce aux 5 % de Wikinews. Pas d'ablation propre de Wikinews seul : effet non démontré isolément.
- Plus d'Assemblée aide le dialogue (M1, M2), mais répéter l'Assemblée 1,8 fois (M2) ne compense pas la perte sur les autres genres.

**Choix soumis** : M4, run officiel relancé avec checkpoint conservé (Colab T4, graine 1337) : **1,3048**, paquet `submissions/2026-11-15_002554`. Le paquet 80/12/8 `2026-11-14_182456` reste intact.

**Limites**
- M1 et M2 sont des lectures de notes orales du mentor (« 35 15 20 30 », parts égales) : interprétation non confirmée par écrit.
- L'Assemblée est répétée dans M1 (1,45 passe), M2 (1,81) et M4 (1,08) ; les autres sources restent en une passe.
- M3 et M5 : une seule graine (M3 relancé sur un autre GPU, même graine). Seul M4 a deux graines.
- Une seule validation publique (230 documents). Le gain vient surtout du littéraire : si le test caché pèse moins ce genre, ou si le style Gutenberg est moins proche de ses textes, le gain caché peut être plus faible.
- Les écarts entre M3, M5 et M4 (~0,011) sont au-dessus du seuil, mais n'ont pas été répétés sur plusieurs graines pour M3 et M5.
