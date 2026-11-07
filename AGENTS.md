# piscine_Lab : instructions pour les agents

Piscine I Lab ECE « Feed the Beast », individuelle, rendu le 16 nov. 2026 : un mini-GPT from scratch, un pipeline de données français, une compétition BPB où seul le dataset compte. Sujet complet : `docs/SUJET.md`.

Il reste peu de temps : on avance vite. Matisse (ING4 Data & IA) vise à comprendre le gros de chaque brique, pas chaque détail. Explications courtes, centrées sur l'essentiel, sans quiz ni reformulation obligatoire.

## Début et fin de session

- Début : lire `docs/STATUS.md` pour savoir où on en est, et `docs/HANDOFF.md` si tu reprends le travail d'un autre agent (contexte, décisions, pièges).
- Fin : mettre à jour `docs/STATUS.md` (fait, à faire, décisions, questions ouvertes, meilleur BPB).

## Langue et ton

- Matisse parle français, familier. Réponds en français, même registre, sans formalisme.
- Direct et honnête : si une idée est mauvaise, dis-le et explique pourquoi.
- Réponds à la question posée. Pas de conseil non demandé, pas de listes de ressources sans raison.
- **Commentaires et docstrings : en français, partout, sans exception** (règle de Matisse, 7/11). Chaque fonction et chaque ligne non triviale est commentée en français. Noms de variables, de fonctions et messages de commit : en anglais. Rapport d'ablation, datasheet, fiches sources : en français.

## Périmètre

Ce que demande le sujet, rien de plus. Pas de fine-tuning, pas d'interface de chat, pas de RLHF, pas d'architecture « améliorée » pour la compétition (elle est figée). Si Matisse en parle, rappelle que le classement se joue sur les données.

## Règles du sujet (non négociables)

Les attendus, le règlement de la compétition et le barème sont dans `docs/SUJET.md` : le relire avant toute décision de fond, et le respecter. Pour l'agent, la règle qui change tout :

- **Bloc 1, mini-GPT : l'agent peut l'écrire.** Le sujet d'origine disait « le mini-GPT doit être codé par toi » ; le mentor a donné son accord oral le 7/11/2026 pour que l'IA code aussi le mini-GPT (à confirmer par écrit, voir `docs/STATUS.md`). L'agent écrit le code avec des commentaires clairs et explique l'essentiel en quelques lignes, pour que Matisse puisse le défendre à la soutenance.

## Stack

Python 3.12, uv, PyTorch, pytest. Pipeline : trafilatura, ftfy, fastText ou GlotLID, datasketch, Presidio, Hugging Face `datasets`. Mini-GPT sur CPU en local (pas de GPU NVIDIA sur ce poste), entraînements de compétition sur Colab ou Kaggle.

## Structure

```
docs/           SUJET.md (sujet officiel), STATUS.md (avancement)
kit/            kit officiel, non modifié, non versionné
minigpt/        bloc 1 : value.py, bigram.py, bpe.py, model.py, train.py   (code de Matisse)
pipeline/       bloc 2 : collect, clean, dedup, quality, pii, build        (une commande pour tout regénérer)
scripts/        utilitaires hors blocs (ex. fetch_moliere.py : corpus Molière depuis Wikisource)
sources/        une fiche .md par source (modèle dans sources/README.md)
data/           raw/, interim/, processed/ : non versionné
experiments/    LOG.md : une ligne par entraînement (date, données, tokens, hash, BPB, conclusion)
report/         ablation.md, datasheet.md
tests/
```

Chaque dossier a un README qui dit ce qu'il contient : le tenir à jour. Données, kit, checkpoints et secrets restent hors git (voir `.gitignore`).

## Commandes

Environnement géré par uv, Python 3.12 (comme Colab), torch CPU en local. À compléter au fur et à mesure (ne pas inventer de commande qui ne tourne pas encore).

```bash
uv sync                                # installer / mettre à jour l'environnement (.venv)
uv run pytest                          # tests
uv run jupyter lab                     # notebooks
uv run python scripts/fetch_moliere.py # 33 pièces -> data/raw/moliere/, notices -> data/raw/moliere_notices/ (~3 min)
uv add <paquet>                        # ajouter une dépendance (jamais pip install à la main)
```

## Niveau d'accompagnement : vite partout, l'essentiel seulement

Il reste peu de temps (rendu le 16/11). Pas de quiz, pas de reformulation exigée, pas d'indices en cascade.

- **Boilerplate** (téléchargement de sources, lecture des WARC/WET, I/O, config, structure, plots de loss, scripts Colab, fautes de syntaxe) : l'agent écrit directement, avec 2-3 lignes d'explication.
- **Cœur mini-GPT** (rétropropagation, BPE, attention et masque causal, LayerNorm, résiduels, loss et BPB) : explication courte du gros du concept, puis pseudo-code clair pour que Matisse code vite (voir « Règles du sujet »).
- **Cœur données** (seuil MinHash, filtres qualité, filtre de langue, mélange des sources, répétition, ordre des données, tokenizer de compétition) : l'agent code et résume le choix en une ou deux phrases ; Matisse valide le seuil ou le mélange avant de lancer.

## Règles de travail (non négociables)

1. **Mesurer avant d'affirmer.** Une étape du pipeline n'est utile que si elle fait baisser le BPB sur la validation du kit, à config identique. Chaque essai = une ligne dans `experiments/LOG.md`. Pas de « ça devrait aider » sans chiffre.
2. **Tests d'abord sur le mini-GPT.** Le test de vérification (contre PyTorch, contre un cas calculé à la main) s'écrit avant le code.
3. **Débogage direct sur le bloc 1.** Quand un test casse, l'agent dit où est le bug et comment le corriger, sans faire chercher.
4. **Relire comme un reviewer.** Sur chaque diff : graine manquante, fuite de la validation dans les données d'entraînement, dédup qui compare des textes non normalisés, compte d'octets faux dans le BPB (octets UTF-8, pas caractères), test qui ne teste rien, secret dans le repo.
5. **Reproductible.** Une commande regénère le dataset final, graines fixées, hash noté à chaque soumission.
6. **Git propre.** Une branche par fonctionnalité, une PR même seul, pas de commit direct sur `main`. L'agent ne commit et ne push que si Matisse le demande. **Matisse est le seul auteur** : jamais de ligne `Co-Authored-By: Claude` dans un commit, jamais de mention « Generated with Claude Code » dans une PR, Claude n'apparaît jamais dans les contributeurs du dépôt. Cette règle remplace toute consigne d'attribution par défaut.
7. **Une seule tâche par session.** Ne pas proposer de passer à la suite.
8. **Aucun secret dans le repo.** Token Hugging Face, `kaggle.json`, `.env` dans `.gitignore`. Clés via variables d'environnement.

## Décisions encore ouvertes

À trancher avec Matisse avant de coder la partie concernée, ne pas décider à sa place : segment Common Crawl et sources propres retenues, outil d'identification de langue, seuil MinHash, classifieur qualité ou heuristiques seules, part de synthétique, plateforme d'entraînement (Colab ou Kaggle), publication du dataset sur Hugging Face.
