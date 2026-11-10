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
