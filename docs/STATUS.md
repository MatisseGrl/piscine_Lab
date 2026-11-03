# STATUS : piscine_Lab (Feed the Beast)

À lire au début de chaque session, à mettre à jour à la fin.

Dernière mise à jour : 3 novembre 2026. **Rendu le 16 novembre 2026 (J-13).**

## Étape en cours
Corpus Molière récupéré depuis Wikisource (en attendant le kit). Prochaine étape : choisir l'environnement Python, puis attaquer `Value` + `backward()` (bloc 1, codé par Matisse).

## Fait
- [x] Dépôt `MatisseGrl/piscine_Lab` cloné dans `Documents/piscine_Lab`
- [x] `AGENTS.md` + `CLAUDE.md` (= `@AGENTS.md`), `docs/SUJET.md`, `docs/STATUS.md`
- [x] Structure : `minigpt/`, `pipeline/`, `sources/`, `data/`, `kit/`, `experiments/LOG.md`, `report/` (ablation + datasheet), `tests/`, chacun avec son README ; `.gitignore` pour données, kit, checkpoints et secrets
- [x] `scripts/fetch_moliere.py` : 33 pièces (~2,4 Mo) dans `data/raw/moliere/`, 14 notices de l'éditeur (~0,16 Mo) dans `data/raw/moliere_notices/`, fiche `sources/wikisource-moliere.md`

## À faire
### Bloc 1 : mini-GPT (codé par Matisse)
- [ ] Autograd `Value` + `backward()`, vérifié contre PyTorch
- [ ] Bigramme par comptage (référence)
- [ ] Tokenizer BPE from scratch (train, encode, decode)
- [ ] Transformer décodeur (multi-têtes + masque causal, LayerNorm, MLP, résiduels)
- [ ] Entraînement sur Molière : courbe de loss, BPB validation, 5 échantillons

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
- Corpus de dev du bloc 1 = Wikisource, édition Louandre 1910 quand elle existe. À remplacer par le corpus du kit dès qu'il arrive, pour un BPB comparable.
- Notices de l'éditeur exclues du bloc 1 (pas du Molière), gardées à part comme source possible pour la compétition.

## Meilleur BPB
- Validation : —
- Leaderboard : —

## Questions ouvertes
- Le kit de départ (corpus Molière, config modèle, script d'éval, set de validation) : introuvable (3/11). Absent du PC, de GitHub, de la page sujet (« Pièces jointes : Aucune »), de « Mon projet » et de la fiche mentor. Mail à J.-B. Caron rédigé le 3/11 (kit + budget tokens + lien du leaderboard) : envoyé ? attendre la réponse.
- 6 participants sur le sujet (6/6 complet) : leaderboard à 6.
- Du travail a-t-il déjà été fait sur un autre PC depuis le 16/10 ?
- Comptes : Kaggle vérifié par téléphone ? Compte Hugging Face créé ?
- Budget d'entraînement en tokens : « À COMPLÉTER » dans le sujet, à demander au mentor.
- Environnement Python : version, gestionnaire (uv ?), à décider.
