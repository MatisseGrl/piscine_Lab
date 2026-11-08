# pipeline : bloc 2

Transforme du web brut en données d'entraînement propres. Chaque étape lit la sortie de la précédente dans `data/` et doit prouver son utilité par une ablation.

| Ordre | Étape | Rôle | Sortie |
|---|---|---|---|
| 1 | collect | télécharger un segment Common Crawl (WET) + les sources propres | `data/raw/` |
| 2 | clean | réparer l'encodage, identifier la langue, retirer le boilerplate | `data/interim/clean/` |
| 3 | dedup | doublons exacts (hash) puis quasi-doublons (MinHash + LSH) | `data/interim/dedup/` |
| 4 | quality | filtres heuristiques et/ou classifieur | `data/interim/quality/` |
| 5 | pii | masquer e-mails, téléphones, adresses, noms | `data/interim/pii/` |
| 6 | build | mélange des sources, tokenizer 8 192, shards, hash du dataset | `data/processed/` |

## Lancer la collecte

```bash
uv run --no-sync python -m pipeline.collect --sample
uv run --no-sync python -m pipeline.collect
```

Le mode `--sample` écrit dans `data/raw/_samples/`. Il récupère le premier Mio du premier WET et du premier Parquet, ainsi que le ZIP XML complet (environ 57 Mio au total hors index). Les fichiers `.prefix` sont des extraits binaires.

La commande complète conserve les 900 WET, les 17 fichiers Parquet et le ZIP dans leurs formats d’origine. Prévoir plusieurs dizaines de Gio pour le segment WET et 4,3 Gio pour Wikipédia. Une relance vérifie puis réutilise les fichiers déjà complets. Elle reprend les fichiers manquants ou invalides depuis le début. La collecte utilise la bibliothèque standard Python.

Les étapes suivantes restent à implémenter.
