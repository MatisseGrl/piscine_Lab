# data

Rien ici n'est versionné, à part ce fichier : les données sont trop lourdes et se regénèrent avec le pipeline.

```
data/
├── raw/          sorties de collect, telles que téléchargées
├── interim/      un sous-dossier par étape (clean, dedup, quality, pii)
└── processed/    dataset final tokenisé + tokenizer, avec son hash
```

La [commande de collecte](../pipeline/README.md) range les sources complètes dans `raw/common_crawl/`, `raw/wikipedia_fr/` et `raw/assemblee_nationale/`. Le mode échantillon utilise exclusivement `raw/_samples/`.

Le hash du dataset final est noté dans `experiments/LOG.md` à chaque soumission.
