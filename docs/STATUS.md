# STATUS : piscine_Lab (Feed the Beast)

À lire au début de chaque session, à mettre à jour à la fin.

Dernière mise à jour : 3 novembre 2026. **Rendu le 16 novembre 2026 (J-13).**

## Étape en cours
Structure du dépôt en place. Prochaine étape : récupérer le kit de départ dans `kit/`, puis choisir l'environnement Python.

## Fait
- [x] Dépôt `MatisseGrl/piscine_Lab` cloné dans `Documents/piscine_Lab`
- [x] `AGENTS.md` + `CLAUDE.md` (= `@AGENTS.md`), `docs/SUJET.md`, `docs/STATUS.md`
- [x] Structure : `minigpt/`, `pipeline/`, `sources/`, `data/`, `kit/`, `experiments/LOG.md`, `report/` (ablation + datasheet), `tests/`, chacun avec son README ; `.gitignore` pour données, kit, checkpoints et secrets

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
- (aucune pour l'instant)

## Meilleur BPB
- Validation : —
- Leaderboard : —

## Questions ouvertes
- Le kit de départ (corpus Molière, config modèle, script d'éval, set de validation) : reçu ? où ?
- Du travail a-t-il déjà été fait sur un autre PC depuis le 16/10 ?
- Budget d'entraînement en tokens : « À COMPLÉTER » dans le sujet, à demander au mentor.
- Environnement Python : version, gestionnaire (uv ?), à décider.
