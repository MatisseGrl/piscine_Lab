# Rapport d'ablation

**Résultat final : 1,2767 BPB** sur la validation publique (M4FINALEXCERPTS, graine 1337 ; 1,2786 en graine 1338), contre 1,3538 pour les données brutes. Le détail des essais de sources est dans la dernière section.

Même modèle, même budget, seules les données changent. Tous les chiffres viennent de `Kaggle submissions/LOG.md` et des `result.json` de chaque run (vérifiés le 14/11/2026).

## Protocole

- **Modèle et entraînement :** configuration figée du kit (`config/official.json`, kit à `3709c85`), graine 1337, 3 052 pas, **100 007 936 tokens vus** par run, une seule passe. Entraînement sur Kaggle (GPU T4).
- **Tokenizer :** un seul, de 8 192 entrées, appris sur 10 Mo du nettoyé avec le mélange 80/12/8 (SHA-256 `b2554a82…2379`). Le même fichier sert à toutes les variantes. Limite : appris sur le nettoyé, ce qui peut l'avantager.
- **Mélange de référence :** 80 % Wikipédia FR, 12 % Common Crawl, 8 % Assemblée nationale, compté en **tokens**, graine 42 pour les tirages.
- **Validation :** les 230 documents publics du kit. BPB = bits de NLL divisés par les **octets UTF-8** (813 051), pas par les caractères. Aucune suite de 13 mots en commun entre l'entraînement et la validation, vérifiée sur chaque variante.

## Résultats

Les cinq premières lignes forment la chaîne de traitement (80/12/8). Les trois dernières comparent des mélanges de sources.

| # | Données | BPB val | Écart vs ligne de comparaison |
|---|---|---:|---|
| 1 | Brut contrôlé | 1,3538 | référence |
| 2 | Nettoyé | 1,3340 | −0,0198 vs 1 |
| 3 | Dédupliqué (exact + MinHash 0,97, Wikipédia plafonnée à 300 000 articles) | 1,3330 | −0,0010 vs 2 |
| 4 | Dédupliqué + PII | 1,3322 | −0,0008 vs 3 |
| 5 | Dédupliqué + qualité + PII | 1,3315 | −0,0014 vs 3 |
| 6 | **Dédupliqué + qualité, 80/12/8 (meilleur du pipeline seul)** | **1,3304** | **−0,0025 vs 3 ; −0,0234 vs 1** |
| 7 | Mélange 74/18/8 (dédup + qualité) | 1,3325 | +0,0020 vs 6 |
| 8 | Mélange parts égales (dédup + qualité) | 1,3362 | +0,0058 vs 6 |

## Quelles étapes ont le plus d'impact ?

**Le nettoyage, de très loin : −0,020 BPB**, soit 85 % du gain total entre le brut et le meilleur run (−0,0234). Il retire l'encodage cassé, les textes non français (96 % des pages Common Crawl rejetées) et le boilerplate web. Le reste de la chaîne apporte ensemble environ 0,004.

Les écarts suivants sont **petits** (0,001 à 0,003 BPB). Le filtre qualité est la meilleure des étapes fines (−0,0025), sur un effet de bord curieux : il ne retire que 221 documents Common Crawl (0,07 % du total), mais Common Crawl pèse 12 % des tokens vus, donc le contenu retiré (pages très courtes ou très répétitives) était sur-échantillonné par rapport à son nombre de documents. Je n'ai pas testé cette explication.

Le mélange compte plus que les étapes fines : 80/12/8 bat 74/18/8 de 0,0020 et les parts égales de 0,0058. Les parts égales obligent aussi à répéter beaucoup de tokens (6,1 M de Common Crawl et 19,5 M de l'Assemblée) : l'écart mélange le choix des proportions et la répétition.

## Lesquelles ne servent à rien ?

- **Le masquage PII n'a pas d'effet démontré sur le BPB.** Seul il donne −0,0008, mais ajouté au filtre qualité il donne +0,0011 (1,3315 contre 1,3304). Un effet qui change de signe selon le contexte est typiquement du bruit. Il reste justifiable par la **protection des données**, pas par le BPB. Le dataset final n'a pas de masquage PII : c'est la version qui score le mieux.
- **La déduplication** apporte un gain réel mais minime (−0,0010) et il est mélangé à autre chose (voir ci-dessous). Elle sert surtout à ne pas apprendre par cœur des textes répétés.

## Échecs, surprises et limites

- **Une seule graine d'entraînement, donc pas de barre d'erreur.** Je n'ai pas mesuré la variabilité d'un run à l'autre. Les écarts de 0,001 à 0,003 sont probablement proches du bruit : je les présente comme des tendances, pas comme des preuves. Seul le nettoyage (−0,020) est largement au-dessus.
- **Nettoyé → dédupliqué n'isole pas la déduplication.** Cette étape inclut aussi le plafonnement de Wikipédia à 300 000 articles (2 205 718 articles retirés par tirage, graine 42), alors que la déduplication elle-même n'a retiré que 3 815 doublons exacts et 199 quasi-doublons (MinHash).
- **Le run 74/18/8 a été importé** d'un notebook : le journal ne précise pas ses étapes de préparation et son hash de dataset n'a pas été fourni. Le STATUS le décrit comme « dédup + qualité » ; à confirmer avant de l'affirmer à l'oral.
- **Tokenizer appris sur le nettoyé** : il peut avantager légèrement cette variante.
- **Le masquage PII est un regex** (e-mail, téléphone, IBAN, URL, IP) : ni noms ni adresses postales. Il ne garantit pas l'anonymat.
- **Filtre de langue peu validé** : le contrôle manuel donne 99/100 sur 100 documents, surtout Wikipédia ; trop petit pour conclure sur Common Crawl.
- **Score caché inconnu** : tous les BPB sont sur la validation publique (230 documents). Le test caché n'est pas connu ; le gain final vient surtout du genre littéraire, donc il dépend du poids de ce genre dans ce test.

## Compétition : mélange de sources, recollage et extraits (14-15/11)

Même protocole (kit `3709c85`, 3 052 pas, 100 007 936 tokens, validation publique). **Bruit mesuré** : la référence 80/12/8 donne 1,3304 / 1,3315 / 1,3270 (moyenne 1,3296, σ 0,0023), donc un écart n'est retenu qu'au-delà de **~0,005**. Deux sources ajoutées : Gutenberg FR et Wikinews FR.

| Étape | BPB (graine 1337 / 1338) | Gain | Verdict |
|---|---|---|---|
| Référence 80/12/8 | 1,3304 / 1,3270 | – | départ |
| **M4** : 40 Wikipédia / 15 CC / 15 Assemblée / 25 Gutenberg / 5 Wikinews | 1,3028 / 1,3066 | −0,025 | gain confirmé (2 graines) |
| M4REFLOW : sauts de ligne internes de Gutenberg recollés | 1,2905 / 1,2938 | −0,011 à −0,013 | gain confirmé |
| M4REFLOWBPE : + BPE 8 192 appris sur le mélange | 1,2874 / 1,2849 | −0,003 de plus | gain faible, additif |
| **M4FINALEXCERPTS : Gutenberg en 1 836 extraits de ~48 000 car. au lieu de 204 livres, même quota** | **1,2767 / 1,2786** | **−0,0085 en moyenne** | **retenu, 2 graines** |

**Ce qui compte.** Gutenberg est la source qui fait baisser le BPB (littéraire : 1,68 → 1,46 au total). Le recollage corrige un artefact de format, et passer de quelques livres entiers à beaucoup d'extraits donne plus de variété au même nombre de tokens. Baisser Wikipédia coûte en encyclopédique (1,31 → 1,37), mais est compensé.

**Essais sans gain ou dégradants** (une graine, sauf mention) : parts égales M2 1,3469 ; ordre des données M4ORDER 1,3106 ; 45 % Wikipédia M4WIKI 1,3115 ; rejeu de tokens M4REPEAT 1,3172 ; classifieur web M4CLASS 1,3044 ; BPE sur 50 Mo 1,2983 / 1,3038 ; Gutenberg à 30 % / 35 % 1,2900 / 1,2842 ; livres permutés 1,2899 ; italiques retirés 1,2851 ; BPE réappris 1,2982 (10 Mo) et 1,2839 (50 Mo), tous dans le bruit ou pires.

**Limites.** M1/M2 viennent de lectures de notes orales du mentor, non confirmées par écrit. Seuls M4, M4REFLOW, M4REFLOWBPE et M4FINALEXCERPTS ont deux graines. Les journaux complets sont dans `Kaggle submissions/LOG.md` ; les courbes, dans `report/courbes/`.
