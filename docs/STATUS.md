# STATUS : piscine_Lab (Feed the Beast)

À lire au début de chaque session, à mettre à jour à la fin.

Dernière mise à jour : 3 novembre 2026. **Rendu le 16 novembre 2026 (J-13).**

## Étape en cours
Kit officiel reçu (3/11) et cloné dans `kit/Piscine/`. Venv finalisé : dépendances du kit ajoutées (`tokenizers`, `tzdata`, `regex` en dev). Tests du kit OK (5 passed, 3/11). Prochaine étape : `Value` + `backward()` (bloc 1, codé par Matisse).

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
- [ ] Autograd `Value` + `backward()`, vérifié contre PyTorch
- [ ] Bigramme par comptage (référence)
- [ ] Tokenizer BPE from scratch (train, encode, decode)
- [ ] Transformer décodeur (multi-têtes + masque causal, LayerNorm, MLP, résiduels)
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
- Budget de tokens du bloc 1 : aucune contrainte (mail du mentor, 3/11). Compétition : 100 M tokens vus, config figée (`kit/Piscine/config/official.json`).

## Meilleur BPB
- Validation : —
- Leaderboard : —

## Questions ouvertes
- Quota GPU Kaggle hebdomadaire (~30 h ?) : pas encore vu où il s'affiche. Le « Kaggle Quota » 10 $/jour concerne Kaggle Benchmarks, pas le GPU.
- Le kit demande de copier son contenu dans le dépôt de travail (*Use this template*) : les soumissions vivent dans `submissions/` du dépôt. Copier `ftb/`, `config/`, `data/validation.jsonl` dans `piscine_Lab` ou travailler à côté ? À trancher avant la première soumission.
- 6 participants sur le sujet (6/6 complet) : leaderboard à 6.
- Du travail a-t-il déjà été fait sur un autre PC depuis le 16/10 ?
