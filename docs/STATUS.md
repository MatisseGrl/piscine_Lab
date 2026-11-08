# STATUS : piscine_Lab (Feed the Beast)

À lire au début de chaque session, à mettre à jour à la fin.

Dernière mise à jour : 8 novembre 2026. **Rendu le 16 novembre 2026 (J-8).**

## Étape en cours
Kit officiel reçu (3/11) et cloné dans `kit/Piscine/`. Venv finalisé : dépendances du kit ajoutées (`tokenizers`, `tzdata`, `regex` en dev). Tests du kit OK (5 passed, 3/11). `Value` + `backward()` fait (7/11, PR #1, 8 tests verts). Bigramme par comptage fait (8/11, branche `feat/bigram` partie de `feat/value`, PR #2) : BPB val de référence **3,3544**. PR #1, #2, #3 mergées sur `main`. Tokenizer BPE fait (8/11, PR #4 mergée) : vocab 1 024, 2,49 octets/token sur la val. Transformer décodeur fait (8/11, branche `feat/model`, PR #5, à merger) : 33 tests verts. Prochaine étape : entraînement sur Molière (`minigpt/train.py`).

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
- [ ] Entraînement sur Molière (`kit/Piscine/corpus/moliere_train.txt`) : courbe de loss, BPB sur `moliere_val.txt` (Misanthrope, Avare, Sicilien) calculé soi-même, 5 échantillons

### Bloc 2 : pipeline de données
- [ ] Collecte : ≥ 1 segment Common Crawl + ≥ 2 sources propres FR, une fiche par source
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
- Modèle (8/11) : config par défaut `GPTConfig()` = 4 couches, 4 têtes, d_model 128, contexte 128 tokens, vocab 1 024, dropout 0 : ~1,07 M paramètres, ~0,3 s par pas (batch 32 x 128) sur le CPU du poste. Proposée par l'agent, à confirmer par Matisse avant `train.py`. Pre-norm (LayerNorm avant chaque sous-couche), tête de sortie non liée aux embeddings, init N(0, 0,02). `evaluate_bpb` : fenêtres consécutives de 128 tokens, le premier token du texte n'est pas prédit (négligeable), bits divisés par les octets UTF-8 du texte entier.
- Budget de tokens du bloc 1 : aucune contrainte (mail du mentor, 3/11). Compétition : 100 M tokens vus, config figée (`kit/Piscine/config/official.json`).

## Meilleur BPB
- Validation (Molière, `moliere_val.txt`) : 3,3544, bigramme d'octets (référence du bloc 1, 8/11)
- Leaderboard : —

## Questions ouvertes
- Quota GPU Kaggle hebdomadaire (~30 h ?) : pas encore vu où il s'affiche. Le « Kaggle Quota » 10 $/jour concerne Kaggle Benchmarks, pas le GPU.
- Le kit demande de copier son contenu dans le dépôt de travail (*Use this template*) : les soumissions vivent dans `submissions/` du dépôt. Copier `ftb/`, `config/`, `data/validation.jsonl` dans `piscine_Lab` ou travailler à côté ? À trancher avant la première soumission.
- 6 participants sur le sujet (6/6 complet) : leaderboard à 6.
- Du travail a-t-il déjà été fait sur un autre PC depuis le 16/10 ?
