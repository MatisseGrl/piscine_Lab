# data

Rien ici n'est versionné, à part ce fichier : les données sont trop lourdes et se regénèrent avec le pipeline.

```
data/
├── raw/          sorties de collect, telles que téléchargées
├── interim/      un sous-dossier par étape (clean, dedup, quality, pii)
└── processed/    dataset final tokenisé + tokenizer, avec son hash
```

Le hash du dataset final est noté dans `experiments/LOG.md` à chaque soumission.
