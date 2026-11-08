# HANDOFF : passation pour un autre agent

Écrit le 7 novembre 2026, mis à jour le 8 pour qu'un autre agent (ou une autre session) reprenne sans rien perdre. Lire dans l'ordre : ce fichier, `AGENTS.md`, `docs/STATUS.md`, `docs/SUJET.md`. Rendu final : **16 novembre 2026**.

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
- PR #1, #2, #3 mergées sur `main` (8/11).
- **Bloc 1, étape 3 : tokenizer BPE terminé (8/11).**
  - Code : `minigpt/bpe.py`, classe `BPETokenizer` (`train(text, vocab_size)`, `encode`, `decode`, `save`, `load`). Niveau octet, pré-découpage en mots par regex, comptage pondéré par mot distinct (rapide : ~70 s pour 768 merges sur 1,5 Mo), encodage avec cache par mot. Lancer : `uv run python -m minigpt.bpe [vocab_size]` (défaut 1 024), écrit `data/processed/bpe_moliere_1024.json`.
  - Tests : `tests/test_bpe.py`, 8 tests (merges à la main sur `"aaabdaaabac"`, aller-retour accents / octets jamais vus / val entière, texte vide, save/load). `uv run pytest` donne 24 passed.
  - **Vocab 1 024**, 2,49 octets/token sur la val. PR #4 mergée.
- **Bloc 1, étape 4 : Transformer décodeur terminé (8/11).**
  - Code : `minigpt/model.py` : `GPTConfig`, `LayerNorm` (à la main), `CausalSelfAttention` (scores, masque `tril` -> -inf, softmax, à la main), `MLP` (GELU), `Block` pre-norm avec résiduels, `GPT` (`forward(idx, targets)` -> logits, loss ; `generate(idx, n, temperature, generator)`), `bits_per_byte(nll_nats, text)` et `evaluate_bpb(model, ids, text)`.
  - Config par défaut : 4 couches, 4 têtes, d_model 128, contexte 128, ~1,07 M paramètres, ~0,3 s/pas (batch 32) sur CPU. À confirmer par Matisse.
  - Tests : `tests/test_model.py`, 9 tests (formes, masque causal, attention comparée à `F.scaled_dot_product_attention` dans le test seulement, LayerNorm vs `nn.LayerNorm` valeurs et gradients, surapprentissage d'un batch < 0,05, BPB par octets sur `"été"`, BPB d'un modèle uniforme, generate reproductible). `uv run pytest` donne 33 passed.
  - PR #5 mergée sur `main` au commit `d135cdf`.
- Commentaires et docstrings de `value.py`, `test_value.py` et `scripts/fetch_moliere.py` traduits en français.
- `AGENTS.md` mis à jour : mode « tout comprendre » retiré, commentaires en français obligatoires.
- **Bloc 1, étape 5 : entraînement Molière terminé (8/11, `feat/train`).**
  - `minigpt/train.py` échantillonne des fenêtres de 128 tokens dans le train du kit, avec des cibles décalées d’un token. AdamW sur CPU, 2 700 pas, batch 32, taux 3e-4, graine 42. Le BPB est mesuré tous les 500 pas et au dernier pas.
  - **BPB final 1,8237**, contre 3,3544 pour le bigramme. 11 059 200 tokens vus, environ 26 minutes avec 4 threads CPU. Le détail et les empreintes des données sont dans `experiments/LOG.md`.
  - Courbe `experiments/moliere_loss.png`, cinq générations à température 0,8 dans `experiments/moliere_samples.txt`, checkpoint ignoré par Git dans `checkpoints/moliere_gpt.pt`.
  - `tests/test_train.py` vérifie le décalage des cibles et la baisse de loss sur un mini-texte. Suite complète : 35 tests réussis.

## Ce qui reste (ordre du sujet, détail dans `docs/STATUS.md`)
1. ~~Bigramme par comptage~~ : fait (BPB val 3,3544).
2. ~~Tokenizer BPE~~ : fait (vocab 1 024).
3. ~~Transformer décodeur~~ : fait (`minigpt/model.py`).
4. ~~Entraînement sur Molière~~ : fait (`minigpt/train.py`, BPB val 1,8237).
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
uv run python -m minigpt.bpe  # seulement si les merges du bloc 1 manquent
uv run python -m minigpt.train
uv run python scripts/fetch_moliere.py
```
