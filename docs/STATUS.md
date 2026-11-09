# STATUS : piscine_Lab (Feed the Beast)

À lire au début de chaque session, à mettre à jour à la fin.

Dernière mise à jour : 9 novembre 2026. **Rendu le 16 novembre 2026 (J-7).**

## Étape en cours
Bloc 1 mergé sur `main` via la PR #6 (`29a181f`, commit d'entraînement `8a5ff57`). Le mini-GPT atteint **1,8237 BPB** sur la validation Molière. Le bloc 1 avait été validé avec 35 tests.

Bloc 2, collecte : `feat/collect` part de `29a181f`. Matisse a validé le segment WET `1736703361941.29` de `CC-MAIN-2025-05`, Wikipédia FR `20231101.fr` à la révision `b4c48878f631fc348dd47a4d89c3d1e4b928a0de` et les débats de la 16e législature (ZIP XML officiel, chemin `16/vp/`).

`uv run --no-sync python -m pipeline.collect --sample` vérifiée le 8/11. Deux enregistrements texte WET lus dans le premier Mio, signature du Parquet vérifiée et métadonnées de trois articles lues à distance sur la révision fixée, ZIP de 57 553 703 octets conforme au MD5 officiel avec 605 XML et un compte rendu lu.

Collecte complète terminée le 9/11 après plusieurs reprises réseau. Dans `data/raw/` : 900 WET (91 791 596 895 octets, tailles HTTP vérifiées), 17 Parquet (4 614 488 286 octets, SHA-256 LFS vérifiés) et un ZIP XML (57 553 703 octets, MD5 officiel vérifié).

## Fait
- [x] Dépôt `MatisseGrl/piscine_Lab` cloné dans `Documents/piscine_Lab`
- [x] `AGENTS.md` + `CLAUDE.md` (= `@AGENTS.md`), `docs/SUJET.md`, `docs/STATUS.md`
- [x] Structure : `minigpt/`, `pipeline/`, `sources/`, `data/`, `kit/`, `experiments/LOG.md`, `report/` (ablation + datasheet), `tests/`, chacun avec son README ; `.gitignore` pour données, kit, checkpoints et secrets
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
- [x] Entraînement CPU sur Molière (`minigpt/train.py`) : 2 700 pas AdamW, batch 32, taux 3e-4, graine 42. Courbe et cinq échantillons dans `experiments/`, checkpoint local dans `checkpoints/moliere_gpt.pt`.

### Bloc 2 : pipeline de données
- [x] Commande de collecte et trois fiches sources, vérifiées sur échantillons réels
- [x] Collecte complète téléchargée et contrôlée
- [ ] Nettoyage : encodage (ftfy), langue (+ précision mesurée sur échantillon annoté main), boilerplate
- [ ] Dédup exacte (hash) + quasi-doublons (MinHash + LSH, seuil justifié)
- [ ] Filtrage qualité + masquage données personnelles
- [ ] Rapport d'ablation (2 pages) : brut vs nettoyé vs complet

### Bloc 3 : compétition
- [ ] Tokenizer 8 192 entraîné sur le mix
- [ ] Soumissions (2/jour) : checkpoint + tokenizer + logs + hash dataset
- [ ] Datasheet (Gebru et al. 2018), dataset sur Hugging Face (bonus)
- [ ] Soutenance

## Décisions
- Environnement : uv + Python 3.12 (même version que Colab). Dépendances du pipeline ajoutées seulement au bloc 2.
- Entraînement du bloc 1 : **uniquement les données du kit** (`kit/Piscine/corpus/moliere_train.txt`, éd. Chasles 1888), rien d'extérieur. BPB sur `moliere_val.txt`. Le corpus Wikisource (`data/raw/moliere/`) et ses notices ne servent pas à l'entraînement (décision de Matisse, 3/11) ; ils contiennent d'ailleurs les 3 pièces de validation du kit.
- Accompagnement (7/11, manque de temps) : fin du mode « tout comprendre » (plus de quiz, de reformulation ni d'indices en cascade). On vise le gros de chaque concept. Mini-GPT : le sujet d'origine (`docs/SUJET.md:42`, commit du 3/11) exigeait qu'il soit codé par Matisse ; le mentor a dit oui à l'oral le 7/11 pour que l'IA le code aussi. L'agent écrit donc le code. **À faire : obtenir cet accord par écrit (mail du mentor) avant le rendu**, et décider si on remet `SUJET.md` dans son état d'origine (Matisse en a modifié la ligne 42 à la main).
- Bigramme (8/11) : sur les **octets** UTF-8 (pas les caractères), donc BPB = moyenne de -log2 p par octet. Lissage de Laplace alpha=1, non réglé sur la val (régler alpha sur la val serait une fuite). Contexte spécial BOS pour le premier octet.
- Fins de ligne : sous Windows, `core.autocrlf=true` ajoute un `\r` par ligne au checkout du kit (+60 k octets en train, +10 k en val). Toujours lire le corpus en mode texte (`minigpt.bigram.load_utf8`, comme `ftb/evaluate.py`) : sinon BPB faussement bas (3,23 au lieu de 3,35 pour le bigramme). Hash vérifié identique au fichier du kit.
- BPE (8/11) : niveau octet (256 de base, tout texte encodable), pré-découpage en mots (regex ` ?\w+| ?[^\w\s]+|\s+`) pour que les merges ne traversent pas deux mots, égalité de fréquence -> paire vue en premier. **Vocab 1 024** (validé par Matisse) : 2,49 octets/token sur la val contre 2,02 pour 512. Entraîné sur `moliere_train.txt` seul. Merges dans `data/processed/bpe_moliere_1024.json` (non versionné, regénéré par `uv run python -m minigpt.bpe` en ~70 s, sha256 9c7ba507e0b0).
- Modèle (8/11) : `GPTConfig()` avec 4 couches, 4 têtes, d_model 128, contexte 128 tokens, vocab 1 024, dropout 0, environ 1,07 M paramètres. Pre-norm, tête de sortie non liée aux embeddings, init N(0, 0,02). `evaluate_bpb` utilise des fenêtres consécutives de 128 tokens et divise les bits par le nombre d’octets UTF-8 du texte entier. Run CPU de référence avec 4 threads, environ 26 minutes avec les évaluations.
- Budget de tokens du bloc 1 : aucune contrainte (mail du mentor, 3/11). Compétition : 100 M tokens vus, config figée (`kit/Piscine/config/official.json`).

## Meilleur BPB
- Validation Molière (`moliere_val.txt`) : **1,8237** pour le mini-GPT, contre **3,3544** pour le bigramme (8/11).
- Leaderboard : —

## Questions ouvertes
- Quota GPU Kaggle hebdomadaire (~30 h ?) : pas encore vu où il s'affiche. Le « Kaggle Quota » 10 $/jour concerne Kaggle Benchmarks, pas le GPU.
- Le kit demande de copier son contenu dans le dépôt de travail (*Use this template*) : les soumissions vivent dans `submissions/` du dépôt. Copier `ftb/`, `config/`, `data/validation.jsonl` dans `piscine_Lab` ou travailler à côté ? À trancher avant la première soumission.
- 6 participants sur le sujet (6/6 complet) : leaderboard à 6.
- Du travail a-t-il déjà été fait sur un autre PC depuis le 16/10 ?
