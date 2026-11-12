# STATUS : piscine_Lab (Feed the Beast)

## Import du run Kaggle 74/18/8 (11/11)

Notebook avec sorties et évaluation JSON archivés dans `Kaggle submissions/`, avec une ligne dans le journal. BPB vérifié identique dans les deux fichiers : **1,3324640181392153** sur 230 documents publics, pour 100 007 936 tokens vus. Le meilleur BPB compétition documenté reste **1,3304248963817598** (qualité, 80/12/8).
À compléter : SHA-256 du dataset et date exacte du run, absents des fichiers fournis. Aucun entraînement relancé et aucun changement de mélange décidé lors de cet import.

À lire au début de chaque session, à mettre à jour à la fin.

Dernière mise à jour le 11 novembre 2026. **Rendu le 16 novembre 2026 (J-5).**

## Priorités avant le rendu (11/11)

- **Compétition.** Six essais à configuration identique sont journalisés (PR #17). Meilleur BPB public : **1,330424896**, variante dédupliquée + qualité, mélange 80/12/8. Aucun dossier de soumission sur `main` lors de la vérification. Retrouver le checkpoint et le tokenizer du run Kaggle, ou relancer le même flux si les poids sont indisponibles. Reste à valider le choix final et à déposer le paquet officiel avec les logs et le hash du flux. BPB caché et classement à confirmer.
- **Ablation.** Finaliser le rapport de deux pages avec les six scores du journal. Le nettoyage donne la plus forte baisse observée (1,353794 → 1,334005). Le passage au dédupliqué inclut aussi le plafonnement de Wikipédia.
- **Langue.** Le script de score confirme **99/100** sur le tirage annoté du corpus nettoyé (graine 42). Le tirage comprend 99 articles Wikipédia et une page Common Crawl. Reporter le résultat dans le rapport ou la datasheet en précisant la composition du tirage.
- **Datasheet et reproductibilité.** La fiche des variantes est sur `main` (PR #15). La finaliser après le choix du flux, avec ses mesures et son empreinte. Les étapes sont documentées séparément. La commande unique de régénération demandée par le sujet reste à fournir et à vérifier.
- **Bloc 1 et soutenance.** Le mini-GPT de base est livré. La continuation est sur `main` (PR #18) à **1,770614 BPB Molière**. La démo terminal demandée par le mentor est locale et le pilote conversationnel a obtenu 0/8 réponses pertinentes. Préparer la soutenance et obtenir la confirmation écrite de l'accord du mentor sur l'usage de l'IA pour le mini-GPT.
- **Essai et bonus.** Le mélange à parts égales est archivé et journalisé à **1,336187 BPB** ; le mélange 74/18/8 atteint **1,332464 BPB**. Le meilleur score reste celui du 80/12/8 avec qualité. La publication Hugging Face est facultative et reste à décider.

Les entrées datées ci-dessous retracent les étapes précédentes.

Résolution des conflits de la PR #21 le 11/11 : conservation des deux archives Kaggle, des deux entrées du journal et des priorités à jour de main.

## Étape en cours

### Comparaison des modèles Molière (12/11)

Meilleur mini-GPT seul à **1,766015 BPB** après moyenne de trois checkpoints. L'ensemble de six checkpoints atteint **1,748069**, puis **1,696002** avec les fréquences du train et des cinq pièces Wikisource contrôlées. Cette dernière mesure exploratoire combine plusieurs modèles et des données supplémentaires. La cible reste **1,500**.

Le SFT avec paraphrases monte à **5/8** sur les réparations de développement, mais la moyenne retenue ne réussit qu'**1/8** sur les relances inédites, comme l'essai de nuit. La démo de la PR #23 reste chargée. Les [commandes et résultats](../report/moliere_model_comparison.md) sont archivés. Les autres continuations de nuit peuvent encore produire des paliers.

### Entraînements de nuit relancés (11/11, 23 h 13)

Les quatre essais tournent en série, dans `runs/night-20261111-231345/` : réparation du chat, continuation sur le kit, dropout et supplément Wikisource. Le premier entraînement est démarré ; aucun score nouveau au lancement. Le lanceur séparé (PID 53688) écrit ses journaux et son statut de fin dans `runs/night-launch-20261111-231342/`. Le meilleur BPB connu reste **1,770614**. Le chat localhost n'a pas été remplacé.

### Reprise Molière mise en pause (11/11)

Matisse vise **1,500 BPB Molière** et a signalé que le chat déraille lorsqu'il lui demande de s'expliquer. Les quatre essais de reprise sont arrêtés sur sa demande. Paliers conservés : continuation du kit au pas 400, **1,790130** ; SFT réparation au pas 250, **1,853007** et **0/8** réparations sur le développement. Le cosinus reste à **1,770614** et la page sert toujours le pas 1 000 de la PR #23. Voir la [reprise de nuit](../report/moliere_restart.md) pour les commandes, les audits et les mesures à terminer.

### Démo locale Molière (11/11)

La démo multi-tour du bloc 1 suit la décision de la PR #20. Le pas 1 000 du SFT v2 avec rappel Molière à 30 % est retenu sur le développement : scénario JB **3/3**, pertinence **16/20**, contexte **7/9**. Sur les discussions inédites : **13/24** pertinentes, **7/13** en contexte et **12/24** avec couleur théâtrale. BPB de ce checkpoint : **1,854847**. Le cosinus reste le meilleur BPB Molière à **1,770614**.

La page localhost a été relancée avec ces poids et testée dans Chrome sur trois tours. Les 135 tests passent. Les générateurs de données, mesures, échecs, commande et PPTX sont décrits dans le [rapport de démo](../report/chat_demo.md). Les poids originaux et nouveaux restent locaux. Limites : noms inédits, reformulations et échanges longs. Le bloc 3 n'est pas modifié par cette démo.

### Mini-GPT Molière (11/11)

Meilleur BPB Molière **1,770614**, après 1 000 pas supplémentaires avec un taux
cosinus de 1e-4 à 1e-5. À taux constant et avec les mêmes tirages, le BPB est
de 1,778539. Le checkpoint de référence (1,823678) est conservé.
Les mesures et les poids de continuation sont dans `runs/moliere-continuation-20261111/`.

Le pilote supervisé (400 pas, 5 920 paires authentiques extraites du train
du kit, loss sur la réponse seule) a échoué. Il atteint **1,889077 BPB** et
**0/8 réponses pertinentes** sur les questions inédites à la graine testée.
Son checkpoint est séparé dans `runs/moliere-dialogue-20261111/`.
Le [rapport Molière](../report/moliere_tuning.md) décrit le protocole et
les générations. Le prochain essai vise le dialogue multi-tour. Le jeu de
données et le checkpoint de la démo suivent le périmètre défini dans
[Décisions](#décisions).

### Run 2 Kaggle — mélange à parts égales (11/11)

Le mélange à parts égales en tokens de Wikipédia FR, Common Crawl et Assemblée
nationale atteint **1,336187 BPB** sur les 230 documents publics après
100 007 936 tokens vus. Le tokenizer et la configuration du kit sont communs
avec le run qualité 80/12/8. Le BPB augmente de 0,005762 et le mélange à parts
égales nécessite de répéter des tokens de Common Crawl et de l'Assemblée.
La référence 80/12/8 avec filtre qualité reste la meilleure sur cette validation.
Le notebook et l'évaluation sont archivés dans `Kaggle submissions/run-02/`.

### Notebook Kaggle (11/11)

L'export Kaggle.ipynb dans le dossier Kaggle submissions regroupe les six essais et leurs sorties. Notebook publié sur main (PR #16). Les six résultats vérifiés sont importés dans Kaggle submissions/LOG.md. Le meilleur BPB sur la validation publique est de 1,330424896 pour la variante dédupliquée avec filtre qualité. Les archives de résultats ne contiennent pas les checkpoints.

### Qualité et masquage PII — sorties produites (10/11)

Seuils et masquage regex validés par Matisse le 10/11. `pipeline/quality.py`, `pipeline/pii.py` et `pipeline/variants.py` écrits avec leurs tests (119 tests verts, dont ablation et ablation_runs). Les quatre variantes sont dans `data/interim/` : dédupliqué (inchangé), `quality/final/`, `pii/dedup/`, `pii/quality/`. Rejets qualité : 221 documents (0,07 %), presque tous Common Crawl. PII : surtout Common Crawl (4 702 e-mails, 6 845 téléphones). SHA-256 relus, zéro recouvrement de 13 mots avec les 230 documents publics. Durée réelle de 9 à 10 min par passe. Détail, commandes et limites dans `pipeline/README.md`. Non commité. BPB non mesuré : les trois runs Kaggle de l'ablation tournent, et ces variantes n'ont ni tokenizer ni entraînement.

### Variantes qualité/PII prêtes pour Kaggle (10/11)

Flux `quality`, `pii` et `quality_pii` construits dans `data/processed/ablation-extra/` avec le tokenizer et le protocole de la série de base (100 007 937 tokens chacun). Archive `data/processed/ablation-extra-kaggle.zip` prête, procédure dans `pipeline/README.md`. Entraînements non lancés : Matisse les fera sur Kaggle plus tard. Trame de `report/ablation.md` remplie, BPB à mesurer.

### Ablation

Ablation sur la validation publique du kit. `main` synchronisée à `cb17d9a` (PR #9, #10 et #11 intégrées), puis branche locale `codex/corpus-ablation`. Les neuf archives d’entrée correspondent aux SHA-256 des trois audits sur les 230 documents publics. Aucun recouvrement de 13 mots n’a été relevé.

Matisse a validé Wikipédia FR 80 %, Common Crawl 12 % et Assemblée nationale 8 %. Le tokenizer commun de 8 192 entrées est entraîné sur un échantillon fixe du nettoyé avec ce mélange en octets UTF-8 (graine 42) et sera réutilisé pour la compétition. Son SHA-256, reproduit à l’identique sur le même échantillon, est `b2554a8221a55c19b4008f5b605b1b6e84b6a7f84058507c15aba34eca3b2379`. Les jeux d’entraînement appliquent le mélange en tokens. Le kit intact, à `3709c85`, fixe la graine d’entraînement à 1337 et arrondit le budget nominal de 100 M à 100 007 936 tokens vus.

Matisse lance les trois entraînements sur Kaggle T4 avec le lanceur de l’ablation. Le mode opératoire et les limites sont dans `pipeline/README.md`. Le journal et l’ébauche chiffrée de `report/ablation.md` attendent les résultats réels.

Les trois flux sont prêts dans `data/processed/ablation/`. La relecture confirme la taille, le dernier lot du lecteur officiel et les SHA-256 ci-dessous. L’archive à importer sur Kaggle est `data/processed/ablation-kaggle.zip`.

| Variante | SHA-256 de `train.bin` |
|---|---|
| Brut | `151ca028be94476949cc43504323741076a017e63ca307dbc2dbc2240962d8f0` |
| Nettoyé | `71c5a146a04676041e37b64d2d7e295a88f64915a304b22e523302c6872a4002` |
| Dédupliqué | `56ee10c62f6d9c2a6c2d48a060c2eae3850819f46c62ecd782a2c0a7ee7faaad` |

### Déduplication terminée
Déduplication sur `feat/dedup`, créée depuis `main` synchronisée au merge de la PR #10 (`6e19b7a`). Les trois fichiers nettoyés sont présents et leurs SHA-256 correspondent au run plafonné.

Le pilote a traité 62 000 documents et en conserve 61 128 après dédup exacte. L'index représente 12,5 Mo de tableaux sur le pilote et environ 66 Mo à taille maximale après le tirage de 300 000 articles Wikipédia. Matisse a validé le seuil Jaccard à 0,97 et le premier représentant conservé dans l'ordre Assemblée, Wikipédia FR, Common Crawl, puis ordre de chaque fichier. Estimation sur ce poste de 45 à 75 min avec la relecture.

Le 10/11, le run intégral sur secteur a abouti en environ 36 min, audit de validation compris. L'exact retire 3 815 doublons internes et aucun entre sources. Après tirage de 300 000 articles Wikipédia, MinHash retire 199 documents et la sortie finale contient 320 319 documents et 1 056 674 469 octets UTF-8. La relecture confirme les compteurs et les SHA-256 des sorties exacte et finale. Aucun recouvrement détecté avec les 230 documents publics. Le détail par source et les empreintes figurent dans `pipeline/README.md`. PR #11 ouverte.

Nettoyage mergé sur `main` via la PR #9 (`56e60a2`). Le test sur les 1 000 premiers documents de chaque source est dans `data/interim/clean-verified/`.

Le 9/11, le premier run a été arrêté pendant Common Crawl et ses sorties partielles ont été supprimées. Parcourir les 91,8 Go compressés aurait pris environ trois jours sur ce poste. Matisse a validé un plafond de 1 050 000 000 octets compressés pour Common Crawl, compte tenu du délai et du budget de 100 M tokens vus en compétition. Le préfixe trié couvre 10 archives WET (1 019 886 136 octets). Wikipédia FR et l'Assemblée passent en entier.

Le run plafonné a abouti le 9/11 avec `uv run python -m pipeline.clean --include-raw --cc-max-bytes 1050000000`. Les sorties et les statistiques sont dans `data/interim/clean/`. Les six fichiers gzip ont été relus et leurs SHA-256 et compteurs concordent avec `stats.json`.

| Source | Documents lus | Documents exportés en brut | Documents nettoyés | Octets UTF-8 nettoyés | Rejets du nettoyé | Rejets par le garde-fou |
|---|---:|---:|---:|---:|---:|---:|
| Common Crawl | 328 200 | 328 199 | 13 017 | 91 030 055 | 96,03 % | 1 |
| Wikipédia FR | 2 564 646 | 2 563 979 | 2 507 940 | 7 647 370 763 | 2,21 % | 666 |
| Assemblée nationale | 11 277 | 9 255 | 9 094 | 56 952 466 | 19,36 % | 2 022 |

Sur les 230 documents de validation publique, aucune séquence de 13 mots en commun, recouvrement moyen de 0,0 et aucun document signalé pour chaque variante. L'audit compare les suites de mots en minuscules avec la même tokenisation que le kit. Ses rapports `audit-raw.json` et `audit-clean.json` sont dans le dossier de sortie. Le garde-fou du pipeline contrôle aussi la validation Molière.

Bloc 1 mergé sur `main` via la PR #6 (`29a181f`, commit d'entraînement `8a5ff57`). Le mini-GPT atteint **1,8237 BPB** sur la validation Molière. Le bloc 1 avait été validé avec 35 tests.

Bloc 2, collecte : `feat/collect` part de `29a181f`. Matisse a validé le segment WET `1736703361941.29` de `CC-MAIN-2025-05`, Wikipédia FR `20231101.fr` à la révision `b4c48878f631fc348dd47a4d89c3d1e4b928a0de` et les débats de la 16e législature (ZIP XML officiel, chemin `16/vp/`).

`uv run --no-sync python -m pipeline.collect --sample` vérifiée le 8/11. Deux enregistrements texte WET lus dans le premier Mio, signature du Parquet vérifiée et métadonnées de trois articles lues à distance sur la révision fixée, ZIP de 57 553 703 octets conforme au MD5 officiel avec 605 XML et un compte rendu lu.

Collecte complète terminée le 9/11 après plusieurs reprises réseau. Dans `data/raw/` : 900 WET (91 791 596 895 octets, tailles HTTP vérifiées), 17 Parquet (4 614 488 286 octets, SHA-256 LFS vérifiés) et un ZIP XML (57 553 703 octets, MD5 officiel vérifié).

## Fait
- [x] Dépôt `MatisseGrl/piscine_Lab` cloné dans `Documents/piscine_Lab`
- [x] `AGENTS.md` + `CLAUDE.md` (= `@AGENTS.md`), `docs/SUJET.md`, `docs/STATUS.md`
- [x] Structure : `minigpt/`, `pipeline/`, `sources/`, `data/`, `kit/`, `Kaggle submissions/LOG.md`, `report/` (ablation + datasheet), `tests/`, chacun avec son README ; `.gitignore` pour données, kit, checkpoints et secrets
- [x] `scripts/fetch_moliere.py` : 33 pièces (~2,4 Mo) dans `data/raw/moliere/`, 14 notices de l'éditeur (~0,16 Mo) dans `data/raw/moliere_notices/`, fiche `sources/wikisource-moliere.md`
- [x] Kaggle `matissegarlot` : téléphone vérifié, notebook de test avec 2× T4 (`nvidia-smi` OK), internet OK (huggingface.co répond 200)
- [x] Environnement uv : Python 3.12.14, torch 2.15 CPU, numpy, matplotlib, tqdm ; dev : pytest, jupyterlab. `uv sync` pour installer
- [x] Hugging Face `MatisseGrl` : compte créé, e-mail validé (pas de token pour l'instant)
- [x] Kit officiel `Meuleur/Piscine` (commit 3709c85) cloné dans `kit/Piscine/`, non modifié : corpus Molière (train 25 pièces 1,6 Mo / val 3 pièces 0,27 Mo), `config/official.json`, `ftb/` (modèle, tokenizer, prepare, train, evaluate, contamination, submit), validation publique 230 docs, notebook Colab

## À faire
### Bloc 1 : mini-GPT (codé par Matisse)
- [x] Autograd `Value` + `backward()`, vérifié contre PyTorch
- [x] Bigramme par comptage (référence) : `minigpt/bigram.py`, octets UTF-8, Laplace alpha=1, BPB val 3,3544 (8/11)
- [x] Tokenizer BPE from scratch (train, encode, decode) : `minigpt/bpe.py`, vocab 1 024, 2,49 octets/token sur la val (8/11)
- [x] Transformer décodeur : `minigpt/model.py` (multi-têtes + masque causal à la main, LayerNorm à la main, MLP GELU, résiduels pre-norm, `generate()` avec température, `evaluate_bpb()` par octets UTF-8) (8/11)
- [x] Entraînement CPU sur Molière (`minigpt/train.py`) : 2 700 pas AdamW, batch 32, taux 3e-4, graine 42. Courbe et cinq échantillons dans `Kaggle submissions/`, checkpoint local dans `checkpoints/moliere_gpt.pt`.

### Bloc 2 : pipeline de données
- [x] Commande de collecte et trois fiches sources, vérifiées sur échantillons réels
- [x] Collecte complète téléchargée et contrôlée
- [x] Nettoyage : encodage (ftfy), français et boilerplate WET, statistiques par source, garde-fou de validation et export brut pour l'ablation
- [x] Terminer le nettoyage avec Common Crawl plafonné et vérifier les statistiques et le recouvrement du brut et du nettoyé
- [x] Annoter le tirage de langue et mesurer la précision (99/100, échantillon majoritairement Wikipédia)
- [x] Mesurer les BPB brut, nettoyé et dédupliqué à configuration identique sur les 230 documents publics
- [x] Dédup exacte (hash) + quasi-doublons (MinHash + LSH, Jaccard 0,97), sorties relues et audit du kit
- [x] Filtrage qualité + masquage données personnelles (sorties produites et BPB mesurés)
- [ ] Rapport d'ablation (2 pages) : brut vs nettoyé vs complet

### Bloc 3 : compétition
- [x] Tokenizer 8 192 commun entraîné sur un échantillon du nettoyé au mélange validé
- [ ] Soumissions (2/jour) : checkpoint + tokenizer + logs + hash dataset
- [ ] Datasheet (Gebru et al. 2018), dataset sur Hugging Face (bonus)
- [ ] Soutenance

## Décisions
- Nettoyage validé par Matisse : fastText `lid.176.bin`, français en tête à partir de 0,80 et motifs de boilerplate WET ciblés. Les lignes de 25 caractères maximum répétées au moins trois fois sont retirées aux bords (cinq lignes non vides de chaque côté).
- Pour l'ablation, le brut et le nettoyé partagent un contrôle des séquences de 13 mots de la validation publique et de la validation Molière. Les débats sont lus par section de séance. Kit officiel complet disponible localement dans `kit/Piscine-official/` à `3709c85`.
- Environnement : uv + Python 3.12 (même version que Colab). Dépendances du pipeline ajoutées seulement au bloc 2.
- Référence du bloc 1. Le mini-GPT de référence est entraîné sur `kit/Piscine/corpus/moliere_train.txt` et évalué sur `moliere_val.txt`. Le checkpoint de référence et le checkpoint cosinus sont conservés.
- Démo conversationnelle (décision de Matisse, 11/11). Le fine-tuning multi-tour peut utiliser un **dataset de dialogues distinct**, avec des échanges tirés du train du kit, des dialogues rédigés ou synthétiques et des sources conversationnelles externes dont la licence permet cet usage. Cette autorisation remplace la décision du 3/11 pour le checkpoint de démo. Documenter les sources, les licences, la part de chaque source et la méthode de génération le cas échéant. Écarter les pièces de validation du kit et les dialogues réservés à l’évaluation. Le corpus Wikisource local contient les trois pièces de validation. Cette décision interne s’applique à la démo. Le règlement du bloc 3 reste applicable à la compétition.
- Accompagnement (7/11, manque de temps) : fin du mode « tout comprendre » (plus de quiz, de reformulation ni d'indices en cascade). On vise le gros de chaque concept. Mini-GPT : le sujet d'origine (`docs/SUJET.md:42`, commit du 3/11) exigeait qu'il soit codé par Matisse ; le mentor a dit oui à l'oral le 7/11 pour que l'IA le code aussi. L'agent écrit donc le code. **À faire : obtenir cet accord par écrit (mail du mentor) avant le rendu**, et décider si on remet `SUJET.md` dans son état d'origine (Matisse en a modifié la ligne 42 à la main).
- Bigramme (8/11) : sur les **octets** UTF-8 (pas les caractères), donc BPB = moyenne de -log2 p par octet. Lissage de Laplace alpha=1, non réglé sur la val (régler alpha sur la val serait une fuite). Contexte spécial BOS pour le premier octet.
- Fins de ligne : sous Windows, `core.autocrlf=true` ajoute un `\r` par ligne au checkout du kit (+60 k octets en train, +10 k en val). Toujours lire le corpus en mode texte (`minigpt.bigram.load_utf8`, comme `ftb/evaluate.py`) : sinon BPB faussement bas (3,23 au lieu de 3,35 pour le bigramme). Hash vérifié identique au fichier du kit.
- BPE (8/11) : niveau octet (256 de base, tout texte encodable), pré-découpage en mots (regex ` ?\w+| ?[^\w\s]+|\s+`) pour que les merges ne traversent pas deux mots, égalité de fréquence -> paire vue en premier. **Vocab 1 024** (validé par Matisse) : 2,49 octets/token sur la val contre 2,02 pour 512. Entraîné sur `moliere_train.txt` seul. Merges dans `data/processed/bpe_moliere_1024.json` (non versionné, regénéré par `uv run python -m minigpt.bpe` en ~70 s, sha256 9c7ba507e0b0).
- Modèle (8/11) : `GPTConfig()` avec 4 couches, 4 têtes, d_model 128, contexte 128 tokens, vocab 1 024, dropout 0, environ 1,07 M paramètres. Pre-norm, tête de sortie non liée aux embeddings, init N(0, 0,02). `evaluate_bpb` utilise des fenêtres consécutives de 128 tokens et divise les bits par le nombre d’octets UTF-8 du texte entier. Run CPU de référence avec 4 threads, environ 26 minutes avec les évaluations.
- Budget de tokens du bloc 1 : aucune contrainte (mail du mentor, 3/11). Compétition : 100 M tokens vus, config figée (`kit/Piscine/config/official.json`).

## Meilleur BPB
- Validation Molière (`moliere_val.txt`) : **1,770614** après continuation, référence mini-GPT **1,823678**, bigramme **3,3544**.
- Validation publique du kit : **1,330424896** pour le flux dédupliqué + qualité (11/11).
- Leaderboard : —

## Questions ouvertes
- Choix du flux final et disponibilité des poids Kaggle pour la soumission.
- Quota GPU Kaggle hebdomadaire (~30 h ?) : pas encore vu où il s'affiche. Le « Kaggle Quota » 10 $/jour concerne Kaggle Benchmarks, pas le GPU.
- Le kit demande de copier son contenu dans le dépôt de travail (*Use this template*) : les soumissions vivent dans `submissions/` du dépôt. Copier `ftb/`, `config/`, `data/validation.jsonl` dans `piscine_Lab` ou travailler à côté ? À trancher avant la première soumission.
- 6 participants sur le sujet (6/6 complet) : leaderboard à 6.
- Du travail a-t-il déjà été fait sur un autre PC depuis le 16/10 ?
