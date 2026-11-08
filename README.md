# piscine_Lab : Feed the Beast

Un mini-GPT codé de zéro, puis le meilleur dataset français possible construit à partir du web brut, pour une compétition où le modèle et le budget de calcul sont les mêmes pour tous : seule la donnée fait la différence.

Piscine individuelle de l'Intelligence Lab de l'ECE Paris, du 16 octobre au 16 novembre 2026. Sujet complet : [`docs/SUJET.md`](docs/SUJET.md).

## Objectifs

| Bloc | Livrable | Métrique |
|---|---|---|
| 1. Mini-GPT from scratch | Autograd `Value`, bigramme, tokenizer BPE, transformer décodeur, entraînement sur Molière | BPB sur la validation, 5 échantillons |
| 2. Pipeline de données | Collecte (Common Crawl + sources FR), nettoyage, déduplication, filtrage qualité, masquage PII | Rapport d'ablation : brut vs nettoyé vs complet |
| 3. Compétition | Dataset final + tokenizer 8 192, entraîné avec la config figée du kit | BPB sur le test set caché |

Le BPB (bits par octet) mesure combien de bits le modèle utilise en moyenne pour encoder chaque octet UTF-8 du texte. Il ne dépend pas du tokenizer, ce qui permet de comparer tous les participants. Plus c'est bas, mieux c'est.

## Avancement

| Bloc | État |
|---|---|
| Mini-GPT | Terminé |
| Pipeline | Collecte implémentée et vérifiée sur échantillons |
| Compétition | À faire |

Détail et prochaines étapes : [`docs/STATUS.md`](docs/STATUS.md). Journal des essais : [`experiments/LOG.md`](experiments/LOG.md).

## Structure

```
├── docs/           SUJET.md (sujet officiel), STATUS.md (avancement)
├── kit/            kit de départ officiel, non modifié, non versionné
├── minigpt/        bloc 1 : autograd, bigramme, BPE, transformer, entraînement
├── pipeline/       bloc 2 : collecte → nettoyage → dédup → qualité → PII → dataset final
├── scripts/        utilitaires (téléchargement du corpus Molière depuis Wikisource)
├── sources/        une fiche par source (origine, licence, volume, période, risques)
├── data/           données brutes, intermédiaires et finales, non versionnées
├── experiments/    journal des essais (LOG.md) et configs d'ablation
├── report/         rapport d'ablation et datasheet du dataset
└── tests/          tests (autograd contre PyTorch, BPE, BPB, étapes du pipeline)
```

## Reproduire

Prérequis : [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                 # environnement Python 3.12 + dépendances
uv run python scripts/fetch_moliere.py  # corpus Molière (33 pièces) depuis Wikisource
uv run pytest                           # tests
uv run --no-sync python -m pipeline.collect --sample  # vérification bornée
uv run --no-sync python -m pipeline.collect           # collecte complète (plusieurs dizaines de Gio)
```

Les autres commandes seront ajoutées au fur et à mesure que le code existe. Objectif : une seule commande pour regénérer le dataset final, graines fixées, hash publié à chaque soumission.

## Données et licences

Chaque source utilisée a sa fiche dans [`sources/`](sources/). Les données elles-mêmes ne sont pas versionnées. Les données personnelles sont masquées avant l'entraînement. La datasheet du dataset final suit *Datasheets for Datasets* (Gebru et al. 2018) : [`report/datasheet.md`](report/datasheet.md).

## Licence

Code sous licence MIT ([`LICENSE`](LICENSE)). Les données gardent la licence de leur source.
