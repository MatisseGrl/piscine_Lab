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

Une commande regénère tout (à écrire). Seuils et graines dans un fichier de config, jamais en dur.
