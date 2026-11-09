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

## Lancer le nettoyage

Depuis la racine du dépôt, installe les dépendances avec `uv sync`. La commande cherche les deux fichiers de validation dans `kit/Piscine`, puis dans `kit/Piscine-official`. Si le kit complet manque, récupère la révision de référence dans un dossier ignoré par Git. L'option `--kit` permet d'indiquer un autre chemin.

```bash
git clone https://github.com/Meuleur/Piscine.git kit/Piscine-official
git -C kit/Piscine-official checkout --detach 3709c85
```

```bash
uv run python -m pipeline.clean --include-raw --cc-max-bytes 1050000000
```

Le plafond Common Crawl prend le plus long préfixe d'archives WET entières dans l'ordre des noms, selon leur taille compressée sur disque. Le plafond ci-dessus retient 10 archives sur le segment collecté. Wikipédia FR et l'Assemblée sont traitées en entier. Les archives sélectionnées et leur volume figurent dans `stats.json`.

La commande vérifie le SHA-256 de fastText `lid.176.bin` et le télécharge si nécessaire. Elle répare le mojibake avec ftfy, retire les lignes autonomes de menu, de cookies et de pied de page des WET, puis garde les textes classés français avec un score d'au moins 0,80. Dans les WET, une ligne normalisée d'au plus 25 caractères qui apparaît au moins trois fois est retirée parmi les cinq premières ou cinq dernières lignes non vides. Un document correspond à une page WET, un article Wikipédia ou une section de séance de l'Assemblée.

La sortie `data/interim/clean/` contient un JSONL gzip par source et `stats.json` avec les volumes UTF-8, les taux de rejet, les motifs et les SHA-256. Le parcours des archives et des documents suit un ordre stable, sans tirage aléatoire. Une relance vers un dossier existant est refusée. Utilise `--out data/interim/clean-rerun` pour régénérer dans un autre dossier. Le dossier final est publié à la fin du traitement.

Pour une vérification bornée sur les vrais fichiers, avec sortie brute facultative pour l'ablation :

```bash
uv run python -m pipeline.clean --limit-per-source 1000 --out data/interim/clean-verified --include-raw
```

Le nettoyage exige les 230 documents de validation publique et le fichier de validation Molière du kit. Il écarte des deux variantes tout document qui contient une séquence de 13 mots de la validation (ou un document de validation entier s'il est plus court). Il compare les mots en minuscules et vérifie aussi les raccords créés par la suppression de lignes. Le seuil d'exclusion est volontairement strict et peut retirer des formules communes. Ce contrôle porte sur le recouvrement textuel détectable par cette méthode.

## Annoter la langue

```bash
uv run python -m pipeline.language_audit sample --size 100
uv run python -m pipeline.language_audit score data/interim/language_annotations.json
```

Le tirage uniforme sans remise utilise la graine 42. Remplis chaque champ `annotation` avec `fr`, `autre` ou `mixte`. La précision divise le nombre de `fr` par le nombre total de documents annotés. Pour travailler sur le test borné, indique `--input data/interim/clean-verified --out data/interim/language_annotations_smoke.json` à la commande `sample`.

## Comparer brut et nettoyé

Ajoute `--include-raw` au nettoyage complet. Le sous-dossier `raw/` contient les textes extraits avant nettoyage, après application du même garde-fou de validation. Les JSONL gzip des deux variantes sont directement lisibles par `ftb.prepare`.

Pour isoler l'effet du nettoyage, réutilise le même tokenizer, entraîné hors validation, la même liste ordonnée de sources, la même configuration officielle et le même budget de tokens dans les deux runs. Contrôle séparément les entrées de chaque run avec `ftb.contamination` et mesure le BPB avec `ftb.evaluate` sur la validation publique. Note les SHA-256, les tokens vus et les deux BPB dans `experiments/LOG.md`.
