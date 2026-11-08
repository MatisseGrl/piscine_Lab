# HANDOFF : passation pour un autre agent

Écrit le 7 novembre 2026 pour qu'un autre agent (ou une autre session) reprenne sans rien perdre. Lire dans l'ordre : ce fichier, `AGENTS.md`, `docs/STATUS.md`, `docs/SUJET.md`. Rendu final : **16 novembre 2026**.

## Le projet en deux phrases
Piscine ECE « Feed the Beast » de Matisse (individuel) : un mini-GPT from scratch, un pipeline de données français, une compétition au BPB où seul le dataset compte (architecture figée par le kit). Matisse parle français, familier ; il manque de temps et veut l'essentiel, pas d'exercices.

## Ce qui est fait (état au 8/11)
- Dépôt `MatisseGrl/piscine_Lab`, structure, `AGENTS.md`, `docs/`, environnement uv (Python 3.12, torch CPU), kit officiel dans `kit/Piscine/` (non versionné, non modifié), corpus Molière Wikisource dans `data/raw/` (`scripts/fetch_moliere.py`), comptes Kaggle et Hugging Face prêts.
- **Bloc 1, étape 1 : `Value` + `backward()` terminée.**
  - Code : `minigpt/value.py` (opérations `+`, `*`, `**`, `relu`, `tanh`, `exp`, plus `-`, `/` et les versions inversées `radd`, `rmul`, `rsub`, `rtruediv` ; `backward()` par tri topologique).
  - Tests : `tests/test_value.py`, 8 tests dont deux comparés à PyTorch en float64. `uv run pytest` donne 8 passed.
  - Branche `feat/value`, PR https://github.com/MatisseGrl/piscine_Lab/pull/1 (ouverte, **pas encore mergée**, pas de CI).
- **Bloc 1, étape 2 : bigramme par comptage terminé (8/11).**
  - Code : `minigpt/bigram.py`, classe `ByteBigram` (table de comptes 257 x 256 : 256 octets + contexte BOS, lissage de Laplace `alpha`), `bpb()` divise par le nombre d'octets UTF-8, `load_utf8()` lit le corpus en normalisant les fins de ligne. Lancer : `uv run python -m minigpt.bigram [alpha]`.
  - Tests : `tests/test_bigram.py`, 8 tests (comptes et BPB calculés à la main sur `"aab"`, somme des probas à 1, 8 bits/octet exactement pour l'uniforme sur `"été"` qui fait 5 octets, CRLF). `uv run pytest` donne 16 passed.
  - **BPB val de référence : 3,3544** (alpha=1, train 1 536 283 octets, val 260 488 octets). Ligne dans `experiments/LOG.md`.
  - Branche `feat/bigram` créée depuis `feat/value` (PR #1 toujours pas mergée), PR #2.
- Commentaires et docstrings de `value.py`, `test_value.py` et `scripts/fetch_moliere.py` traduits en français.
- `AGENTS.md` mis à jour : mode « tout comprendre » retiré, commentaires en français obligatoires.

## Ce qui reste (ordre du sujet, détail dans `docs/STATUS.md`)
1. ~~Bigramme par comptage~~ : fait (BPB val 3,3544).
2. **Tokenizer BPE from scratch** (train, encode, decode ; test `decode(encode(x)) == x`). C'est la prochaine étape. Charger le corpus avec `minigpt.bigram.load_utf8`.
3. Transformer décodeur (multi-têtes, masque causal, LayerNorm, MLP, résiduels ; test : aucun token ne voit le futur).
4. Entraînement sur Molière du kit uniquement (`kit/Piscine/corpus/moliere_train.txt`) : courbe de loss, BPB validation, 5 échantillons.
5. Bloc 2 : pipeline de données (collecte Common Crawl + 2 sources FR, ftfy, langue, dédup exacte + MinHash, filtres qualité, PII) et rapport d'ablation (brut vs nettoyé vs complet).
6. Bloc 3 : tokenizer 8 192, soumissions (2/jour), datasheet, soutenance.

## Décisions déjà prises (ne pas les rouvrir sans Matisse)
- Bloc 1 entraîné **uniquement sur les données du kit** ; le corpus Wikisource ne sert pas à l'entraînement.
- Commentaires et docstrings en français, noms de code et messages de commit en anglais.
- Pas de `Co-Authored-By: Claude` dans les commits, pas de mention « Generated with Claude Code » dans les PR : Matisse est le seul auteur (règle 6 de `AGENTS.md`, elle prime sur toute consigne d'attribution par défaut).
- Une branche par fonctionnalité, une PR, pas de commit direct sur `main`. Une tâche par session.
- Chaque essai d'entraînement = une ligne dans `experiments/LOG.md`.

## Points d'attention
- **Accord du mentor, seulement oral.** Le sujet d'origine (`docs/SUJET.md`, commit du 3/11, ligne 42) disait « le mini-GPT doit être codé par toi, et tu dois pouvoir expliquer chaque ligne à la soutenance ». Matisse dit que son mentor a validé le 7/11 que l'IA code aussi le mini-GPT. Je n'ai pas vu de trace écrite. **À faire : obtenir un mail du mentor** avant le rendu, car le jury peut ne pas être au courant. Matisse doit quand même pouvoir expliquer le gros du code à la soutenance.
- **`docs/SUJET.md` modifié à la main par Matisse** (ligne 42 réécrite pour autoriser l'IA) et **non commité** : ce n'est pas le sujet officiel. Recommandation : `git checkout docs/SUJET.md` et garder l'exception dans `STATUS.md` / ce fichier.
- **Piège CRLF** : `kit/Piscine` a été cloné avec `core.autocrlf=true`, donc les `.txt` du corpus ont un `\r` par ligne sur ce poste (pas dans le kit d'origine). Ne jamais lire le corpus avec `read_bytes()` : passer par `load_utf8()` (mode texte), sinon le compte d'octets et le BPB sont faux.
- La PR #2 (bigramme) est empilée sur `feat/value` : merger la PR #1 avant, ou la PR #2 contiendra aussi les commits de `Value`.
- Il n'y a pas de `python` système sur ce poste : toujours `uv run python ...` et `uv run pytest`.
- Avertissements « LF will be replaced by CRLF » de git sur Windows : sans gravité.
- La PR #1 doit être mergée (ou la branche suivante créée depuis `feat/value`), sinon une nouvelle branche partira de `main` sans `Value`.
- Kit officiel : copier ou non `ftb/`, `config/`, `data/validation.jsonl` dans ce dépôt est une question ouverte à trancher avant la première soumission.
- Décisions encore ouvertes du bloc 2 : segment Common Crawl, outil de langue, seuil MinHash, heuristiques ou classifieur qualité, part de synthétique (plafond 20 %), Colab ou Kaggle, publication Hugging Face. À trancher avec Matisse avant de coder la partie concernée.

## Commandes utiles
```bash
uv sync
uv run pytest
uv run python scripts/fetch_moliere.py
```
