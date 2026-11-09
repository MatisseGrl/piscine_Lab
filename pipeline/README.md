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

## Dédupliquer le nettoyé

Les entrées sont les trois JSONL gzip et le `stats.json` de `data/interim/clean/`. Le pipeline contrôle leurs SHA-256 et la sélection Common Crawl du nettoyage plafonné. La déduplication exacte compare des SHA-256 du texte en minuscules, en NFC, avec des espaces uniformisés. Elle garde la ligne du premier représentant, y compris le texte et les métadonnées d'origine. Les rejets exacts sont comptés par source du texte retiré et séparés selon que le représentant vient de cette même source ou d'une autre.

L'ordre validé est Assemblée nationale, Wikipédia FR, Common Crawl, puis l'ordre du fichier dans chaque source. Les sources propres passent donc en priorité. Si une page Common Crawl est déjà représentée par un article Wikipédia écarté au tirage, ce groupe de doublons peut disparaître de la sortie finale.

```bash
uv run python -m pipeline.dedup pilot
uv run python -m pipeline.dedup all --threshold 0.97
```

Le pilote tire 50 000 articles Wikipédia, 6 000 pages Common Crawl et 6 000 sections de l'Assemblée, à graine 42, avant la dédup exacte du lot. Il compare les seuils 0,75, 0,80, 0,85, 0,90, 0,96 et 0,97. Les compteurs, la taille des tableaux de l'index et les identifiants de paires inspectables sont dans `data/interim/dedup-pilot/`.

Sur ce lot, l'exact a retiré 797 documents de l'Assemblée, 6 de Wikipédia et 69 de Common Crawl. Les 872 rejets sont internes aux sources. Les signatures et l'index ont pris 168 s pour les 61 128 survivants, avec 12,5 Mo de tableaux, soit environ 66 Mo pour 322 111 documents. Le test de débit de l'exact traite 49 994 lignes représentatives en 24,3 s, hors parcours du grand gzip Wikipédia. Le traitement complet et sa relecture sont estimés à 45–75 min.

L'inspection du pilote montre des cas distincts à 0,955 (article 2 bis ou 2 dans deux interventions de l'Assemblée) et à 0,889 (deux woredas différents sur Wikipédia). Deux ordres du jour qui diffèrent seulement par un espace après un point atteignent 1,000. Le seuil validé est 0,97. Un seuil élevé réduit les fusions de textes qui partagent un gabarit, avec un risque résiduel si un détail significatif occupe peu de mots.

| Seuil | Retraits Assemblée | Retraits Wikipédia | Retraits Common Crawl |
|---|---:|---:|---:|
| 0,75 | 62 | 673 | 203 |
| 0,80 | 43 | 527 | 158 |
| 0,85 | 20 | 382 | 114 |
| 0,90 | 13 | 276 | 69 |
| 0,96 | 2 | 26 | 21 |
| 0,97 | 2 | 5 | 15 |

À 0,97, le pilote retire encore des contenus distincts qui partagent un gabarit, dont les villages Lug et Medovići (0,975) et deux spectacles du site OARA (0,979). Une paire de captures de la même FAQ à 0,998 ne diffère que par l'heure affichée. Les paires inspectées servent à illustrer les limites du seuil, sans estimation de la précision sur tout le corpus.

En traitement complet, la dédup exacte couvre les 2 530 051 documents. MinHash prend ensuite tous les survivants de Common Crawl et de l'Assemblée et tire 300 000 survivants Wikipédia sans remise, à graine 42, dans leur ordre d'origine. Le sous-échantillonnage et les rejets MinHash sont comptés séparément. L'index MinHash utilise 96 minima, répartis en 16 bandes de six. Une bande commune propose une paire. Le retrait exige un Jaccard exact au moins égal au seuil sur les suites de cinq mots et un représentant déjà conservé. L'index peut manquer des paires similaires qui ne partagent aucune bande.

Le traitement complet vérifie le secteur sous Windows. La sortie exacte est conservée dans `data/interim/dedup/exact/`. Après une interruption de MinHash, on peut repartir de cette étape sans refaire le hash exact.

```bash
uv run python -m pipeline.dedup minhash --threshold 0.97
```

Les fichiers de `data/interim/dedup/final/` sont publiés ensemble après relecture. Le rapport donne les documents, octets UTF-8 et SHA-256 par source, ainsi que le résultat du contrôle des séquences du kit sur les 230 documents publics. Une exécution vers une sortie finale existante est refusée.
