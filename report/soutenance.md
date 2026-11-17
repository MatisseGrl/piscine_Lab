# Fiche de soutenance : Feed the Beast

Matisse Garlot, ECE IA Lab. Rendu le 16/11/2026. Tous les chiffres sont dans `Kaggle submissions/LOG.md` ; ce qui n'est pas encore connu est marqué « à compléter ».

## En une minute

Un mini-GPT codé from scratch (bloc 1), un pipeline de données français (bloc 2), une compétition où seul le dataset change (bloc 3, BPB sur validation). Résultat principal : le **nettoyage** fait presque tout le gain du pipeline (1,3538 → 1,3340) ; le **mélange de sources** (Gutenberg, Wikinews), le recollage et le découpage en extraits amènent le dataset final à **1,2767 BPB**. En plus, une démo de chat « façon Molière » demandée par JB.

## 1. Comment j'ai fait mon dataset

- **Sources** : Wikipédia FR (Wikimedia, instantané du 01/11/2023), Common Crawl (`CC-MAIN-2025-05`, 10 archives WET), débats de l'Assemblée nationale (16e législature). Pour la version finale s'ajoutent Gutenberg FR (25 %) et Wikinews FR (5 %). Pas de crawl maison, pas de synthétique. Fiches dans `sources/`.
- **Pipeline** : collecte → nettoyage (ftfy, fastText ≥ 0,80 pour le français, boilerplate) → déduplication (exacte, puis MinHash au seuil Jaccard 0,97) → filtre qualité (heuristiques) → mélange et tokenisation.
- **Mélange** : 80 % Wikipédia, 12 % Common Crawl, 8 % Assemblée, comptés en **tokens** (pas en documents). Wikipédia est plafonnée à 300 000 articles : sans cela elle écrase tout.
- **Tokenizer** : BPE de 8 192 entrées, identique pour toutes les variantes (sinon la comparaison est faussée).
- **Fuite de validation** : tout document partageant 13 mots consécutifs avec la validation publique du kit est écarté (666 articles Wikipédia, 2 022 sections de l'Assemblée, 1 page web). Contrôlé sur chaque variante.
- **Dataset final** : dédup + qualité 80/12/8, 320 098 documents, ~1,05 Go de texte, SHA-256 `f6ad793c…c9cf`.

## 2. Comment j'ai fait mon ablation

Huit entraînements, **même config du kit, même tokenizer, même graine 1337, 100 007 936 tokens**, seules les données changent.

| Données | BPB |
|---|---:|
| Brut contrôlé | 1,3538 |
| Nettoyé | 1,3340 |
| Dédupliqué | 1,3330 |
| Dédup + PII | 1,3322 |
| Dédup + qualité + PII | 1,3315 |
| Dédup + qualité 80/12/8 | 1,3304 |
| Mélange M4 (+ Gutenberg, Wikinews) | 1,3028 |
| + recollage Gutenberg | 1,2905 |
| + BPE sur le mélange | 1,2874 |
| **+ extraits Gutenberg (final)** | **1,2767** |
| Mélange 74/18/8 | 1,3325 |
| Mélange parts égales | 1,3362 |

À dire : le nettoyage fait −0,020, le reste 0,001 à 0,003, **probablement proche du bruit** (une seule graine, pas de barre d'erreur). Nettoyé → dédupliqué inclut aussi le plafonnement de Wikipédia. Le PII change de signe selon le contexte : il se justifie par la protection des données, pas par le BPB, donc il n'est pas dans le dataset final. Détail : `report/ablation.md`.

## 3. Ce que j'ai fait sur Kaggle

- Les entraînements d'ablation (3 052 pas, GPU T4, environ 13 min chacun), notebooks archivés dans `Kaggle submissions/`.
- Le pré-entraînement du mini-GPT du bloc 1 sur le dataset final pour la démo (`minigpt/pretrain.py`) : résultat à compléter.
- Soumission officielle (`python -m ftb.submit`, paquet envoyé au mentor, qui le teste sur sa machine) : **à compléter**. Score test caché : **à compléter**.

## 4. Mes tests

- **Bloc 1** : tests écrits avant le code (`tests/test_value.py`, `test_bigram.py`, `test_bpe.py`, `test_model.py`, `test_train.py`), comparés à PyTorch ou à un cas calculé à la main. Le compte d'octets du BPB est vérifié en **octets UTF-8** (et non en caractères).
- **Pipeline** : un fichier de tests par étape (`test_clean.py`, `test_dedup.py`, `test_quality.py`, `test_pii.py`), plus les tests de l'ablation (`test_ablation*.py`, `test_variants.py`) et de l'audit de langue.
- **Démo** : tests du fine-tuning et des conversations (`test_finetune.py`, `test_conversation.py`, `test_dialogue.py`).
- Limite honnête : un test qui passe ne prouve pas que le filtre est bon ; la qualité des filtres se juge par le BPB, pas par les tests.

## 5. Mes choix, et mes échecs

Choix : seuil MinHash élevé (0,97) après inspection d'un pilote, pour ne pas fusionner des textes qui partagent juste un gabarit ; mélange compté en tokens ; un seul tokenizer ; ablation d'abord, jugement ensuite.

Échecs :
- Premier SFT sur 5 920 paires extraites du théâtre : **0 réponse pertinente sur 8** (les répliques dépendent d'une scène absente). Abandonné pour des dialogues courts et autonomes.
- Reprises prolongées de l'entraînement Molière : le BPB remonte après le pas 400 (1,7901 → 1,8896), un meilleur palier mais une qualité de dialogue pas meilleure.
- Chat : un bon BPB ne suffit pas à bien dialoguer ; les réparations de dialogue donnent au mieux 1/8 sur des cas inédits. Le prototype tient le scénario de JB mais reste fragile en conversation libre.
- Un modèle « ensemble » à 1,696 BPB Molière est **exploratoire** (fréquences réglées sur la validation) : je ne le présente pas comme résultat. Le résultat propre est 1,4111 (mini-GPT pré-entraîné sur le dataset puis repris sur Molière).
- OpenAssistant/oasst1 examiné puis **écarté** : 37 candidats après filtre, plusieurs réponses hors sujet ou datées.

## 6. Résultats

- Bloc 1, Molière : bigramme 3,3544, mini-GPT sur Molière seul 1,8237, pré-entraîné sur le dataset puis repris sur Molière **1,4111** (chat v5 : 1,4291). Conversations inédites : 2/24 réponses pertinentes (v5), 5/24 avec 3× plus de tokens.
- Compétition (validation publique du kit) : **1,2767** pour le dataset final M4FINALEXCERPTS (1,2786 en graine 1338) ; référence 80/12/8 à 1,3304 ; test caché, rang : à compléter.
- Démo : chat Molière local sur page HTML ; version finale à compléter.

## Questions probables du jury (réponse en 2 lignes)

**Pourquoi le nettoyage pèse-t-il autant et la dédup si peu ?** Le brut contient de l'encodage cassé, du non-français (96 % des pages Common Crawl) et du boilerplate, qui coûtent des bits. Les doublons sont rares une fois Wikipédia plafonnée (3 815 exacts, 199 MinHash).

**Vos écarts de 0,001 sont-ils significatifs ?** Probablement pas : une seule graine, pas de barre d'erreur. Seul −0,020 est clairement hors bruit. Je les présente comme des tendances.

**Pourquoi 80/12/8 ?** Wikipédia est propre et proche de la validation ; Common Crawl apporte la diversité, l'Assemblée l'oral. 80/12/8 bat 74/18/8 (+0,0020) et les parts égales (+0,0058, avec beaucoup de répétition).

**Pourquoi MinHash à 0,97 ?** Plus bas, des textes qui partagent un gabarit étaient fusionnés dans le pilote. C'est un choix par inspection, pas optimisé par ablation.

**Le PII sert-il ?** Pas pour le BPB (−0,0008 seul, +0,0011 avec la qualité). Il protège des e-mails et téléphones, mais c'est un regex : ni noms ni adresses ne sont masqués.

**Comment évitez-vous la fuite de validation ?** Filtre de 13 mots consécutifs avec les 230 documents publics, vérifié sur chaque variante. Il ne voit pas les paraphrases.

**Pourquoi le BPB et pas la perplexité ?** Le BPB divise par les octets UTF-8, donc il est indépendant du tokenizer et comparable entre données.

**Expliquez l'attention causale.** Chaque token calcule des scores avec tous les tokens précédents ; un masque triangulaire met −∞ sur le futur avant le softmax, donc le modèle ne peut pas tricher.

**Qu'est-ce qui est de vous dans le code ?** Le mentor a donné son accord pour que l'IA écrive aussi le mini-GPT (7/11, à garder par écrit). Je dois savoir défendre chaque brique : autograd, BPE, bloc transformer, loss et BPB.

**Les données Molière et dialogues pour la démo, d'où viennent-elles ?** Molière : Projet Gutenberg via le kit, domaine public. Dialogues : gabarits rédigés avec un assistant IA puis déclinés par script, licence MIT. Pas utilisés pour la compétition.

**Qu'est-ce que vous referiez avec plus de temps ?** Plusieurs graines pour une barre d'erreur ; un filtre de langue mieux validé sur Common Crawl ; isoler le plafonnement Wikipédia de la dédup ; publier le dataset sur Hugging Face.
