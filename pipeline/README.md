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

Pour isoler l'effet du nettoyage, réutilise le même tokenizer, entraîné hors validation, la même liste ordonnée de sources, la même configuration officielle et le même budget de tokens dans les deux runs. Contrôle séparément les entrées de chaque run avec `ftb.contamination` et mesure le BPB avec `ftb.evaluate` sur la validation publique. Note les SHA-256, les tokens vus et les deux BPB dans `Kaggle submissions/LOG.md`.

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

### Résultat intégral du 10 novembre 2026

Les volumes en octets portent sur le texte UTF-8. Le tirage retire 2 205 718 articles Wikipédia après l'exact. Ses 300 000 articles totalisent 912 631 767 octets UTF-8 avant MinHash.

| Source | Avant dédup (docs / octets) | Après l'exact (docs / octets) | Après MinHash (docs / octets) | Rejets exacts internes / entre sources | Rejets MinHash |
|---|---:|---:|---:|---:|---:|
| Assemblée nationale | 9 094 / 56 952 466 | 7 716 / 56 776 613 | 7 705 / 56 773 787 | 1 378 / 0 | 11 |
| Wikipédia FR | 2 507 940 / 7 647 370 763 | 2 505 718 / 7 646 942 693 | 299 873 / 912 560 196 | 2 222 / 0 | 127 |
| Common Crawl | 13 017 / 91 030 055 | 12 802 / 89 330 115 | 12 741 / 87 340 486 | 215 / 0 | 61 |
| Total | 2 530 051 / 7 795 353 284 | 2 526 236 / 7 793 049 421 | 320 319 / 1 056 674 469 | 3 815 / 0 | 199 |

Le run a pris environ 36 min jusqu'à la publication, dont 655 s pour les signatures et la construction de l'index, 101 s pour les comparaisons et 209 s pour la vérification finale. Les tableaux de l'index représentent 65 385 672 octets. La relecture des deux étapes confirme les compteurs et les SHA-256. Aucune séquence de 13 mots en commun avec les 230 documents publics du kit, recouvrement moyen 0,0 et zéro document signalé.

| Source | SHA-256 exact | SHA-256 final |
|---|---|---|
| Assemblée nationale | `e6b4521bf58d0cb7bf3633ff558dc17ca33a7f71e241385a9695f93cc3ae6c46` | `57153b1fc0f81040f3f4e2c41fd7a1c7bc31df9adee0b8f4f6307037e24a54a1` |
| Wikipédia FR | `d7fc0ae92176f992adbd00987920846ec88278d9553760977255b0db79b07569` | `e0caf30fa7e9e9477e573059e3b42d9b2fbfddfee847460da87018576027c86e` |
| Common Crawl | `4e003821e53436674a49f0ee75894db66a09e34106d9cc23e53b8f2355735040` | `ab743e79652a4b88e0e557a8ea16419b8138bad550ed7f7e3f5dd8d9a7fd74c9` |

## Qualité et masquage PII (10 novembre 2026)

Règles validées par Matisse. **Qualité** (heuristiques seules, premier motif atteint gagne) : `low_letters` (moins de 30 % de lettres parmi les caractères hors espaces, trois sources), puis pour Common Crawl seulement `too_short` (moins de 100 caractères hors espaces) et `repeated_lines` (à partir de 10 lignes non vides, plus de 60 % de lignes déjà vues dans le document). Ponctuation et longueur moyenne des mots sont mesurées sans rejeter. **PII** (regex seules, marqueurs `[EMAIL]`, `[TEL]`, `[IBAN]`, `[URL]`, `[IP]`) : e-mails, téléphones français, IBAN français à clé modulo 97 valide, URL en HTTP(S) ou `www`, IPv4 et IPv6 valides. Le texte hors segments ciblés reste identique. Noms et adresses postales ne sont pas détectés.

Quatre variantes comparables, toutes dérivées de `data/interim/dedup/final/` (le dédupliqué) sans écraser aucune sortie existante :

```bash
uv run --no-sync python -m pipeline.quality                                   # dédupliqué -> quality/final
uv run --no-sync python -m pipeline.pii                                       # dédupliqué -> pii/dedup
uv run --no-sync python -m pipeline.pii --src data/interim/quality/final --out data/interim/pii/quality   # qualité puis PII
```

Options : `--limit N` (pilote sur les N premiers documents par source, écrit une projection de durée), `--src`, `--out` (dossier neuf obligatoire), `--kit`. Le traitement complet exige le secteur sous Windows. Chaque étape vérifie le SHA-256 de l'entrée, relit la sortie (documents, octets UTF-8, SHA-256), cherche toute suite de 13 mots des 230 documents publics et ne publie qu'à zéro recouvrement. Le code commun est dans `pipeline/variants.py`.

| Variante | Dossier | Documents | Octets UTF-8 |
|---|---|---:|---:|
| Dédupliqué (référence) | `dedup/final/` | 320 319 | 1 056 674 469 |
| Qualité seule | `quality/final/` | 320 098 | 1 053 824 598 |
| PII seule | `pii/dedup/` | 320 319 | 1 055 854 450 |
| Qualité puis PII | `pii/quality/` | 320 098 | 1 053 018 328 |

Rejets qualité par source (documents avant → après) : Assemblée 7 705 → 7 705, Wikipédia FR 299 873 → 299 873, Common Crawl 12 741 → 12 520 (`too_short` 52, soit 0,41 % ; `repeated_lines` 165, soit 1,30 % ; `low_letters` 4, soit 0,03 %). Le filtre ne touche donc presque que Common Crawl et retire 221 documents au total (0,07 %) : son effet sur le BPB sera faible. Moyennes mesurées (non rejetantes) sur les gardés : ponctuation 4,4 % / 4,0 % / 3,7 % et mots de 4,78 / 4,97 / 5,22 caractères (Assemblée / Wikipédia / Common Crawl).

Segments masqués (identiques pour les deux variantes PII, sauf Common Crawl après qualité), documents concernés entre parenthèses, sur le dédupliqué : Assemblée URL 2 (2) ; Wikipédia URL 9 326 (6 061), e-mail 30 (17), téléphone 43 (29), IP 1 782 (62) ; Common Crawl URL 6 252 (2 193), e-mail 4 702 (3 066), téléphone 6 845 (2 775), IP 96 (35), IBAN 2 (2). Common Crawl porte l'essentiel des données personnelles. Les 1 782 IP de Wikipédia se concentrent dans 62 documents, surtout des IPv4 d'articles techniques. Le masquage raccourcit les textes de 0,42 Mo pour Wikipédia, 0,40 Mo pour Common Crawl et de 25 octets pour l'Assemblée.

Contrôles : SHA-256 des trois sorties relus et conformes à leurs `stats.json`, zéro recouvrement de 13 mots avec les 230 documents publics sur chacune. Durées sur secteur : qualité 9,8 min, PII 9,0 min (dédupliqué) et 8,4 min (après qualité) ; le pilote de 3 000 documents par source avait projeté 10,8 et 9,2 min. Les `stats.json` contiennent aussi des exemples par règle (identifiant et extrait) : les extraits de texte passent par le masquage, et les exemples PII ne donnent que la forme du segment (lettres « a », chiffres « 9 »).

Limites : regex seulement, donc pas de noms ni d'adresses ; une version logicielle du type `3.10.2.1` est masquée comme une IP ; les IPv6 très courtes (moins de 5 caractères) ne le sont pas ; un numéro suivi de lettres ou chiffres collés n'est pas masqué par prudence. Aucun BPB n'est mesuré ici : l'effet de la qualité et du PII reste à mesurer à configuration identique après les trois runs Kaggle de l'ablation.

## Ablation sur la validation publique du kit

Mélange validé par Matisse le 10/11/2026. Wikipédia FR 80 %, Common Crawl 12 %, Assemblée nationale 8 %. Pour le tokenizer BPE commun de 8 192 entrées, ces proportions s’appliquent à un échantillon fixe de 10 Mo du nettoyé, en octets UTF-8. Pour l’entraînement, elles s’appliquent aux tokens cibles, y compris les séparateurs de document. Le tirage et le mélange des blocs par fenêtre utilisent la graine 42. Le kit entraîne avec la graine 1337.

Depuis ce checkout, préparer les données et le tokenizer, puis créer l’archive Kaggle.

```powershell
uv run --no-sync python -m pipeline.ablation
uv run --no-sync python -m pipeline.ablation_runs bundle
```

Depuis un autre checkout Windows, on peut lire directement les fichiers existants avec les chemins absolus.

```powershell
uv run --no-sync python -m pipeline.ablation --interim "C:/Users/mgarl/OneDrive/Documents/ChatGPT/piscine_lab/data/interim" --kit "C:/Users/mgarl/OneDrive/Documents/ChatGPT/piscine_lab/kit/Piscine-official"
```

Les entrées sont `clean/raw/`, `clean/` et `dedup/final/`, sous `data/interim/`. La préparation exige les empreintes des neuf archives auditées et l’empreinte de la validation publique associée. Les trois audits ne relèvent aucune séquence commune de 13 mots sur les 230 documents. La préparation refuse un dossier de sortie déjà existant. Les flux binaires, leurs SHA-256, les quotas et le tokenizer sont dans `data/processed/ablation/`. Chaque source est tirée sans remise et son flux de tokens est découpé aux limites de ses quotas dans les fenêtres de mélange du kit. Ces coupures peuvent tomber au milieu d’un document.

### Lancement manuel sur Kaggle

Importer `data/processed/ablation-kaggle.zip` comme entrée privée du notebook, activer Internet et sélectionner un accélérateur T4. Utiliser la même session GPU pour les trois variantes. Dans les commandes ci-dessous, remplacer le chemin d’entrée par celui que Kaggle affiche.

```bash
%cd /kaggle/working
!unzip -o /kaggle/input/CHEMIN/ablation-kaggle.zip
!git clone https://github.com/Meuleur/Piscine.git kit
!git -C kit checkout --detach 3709c85ddaabfcd688d6eea80a5c5ed90605b549
%pip install tokenizers==0.23.3
!python -m pipeline.ablation_runs run --kit kit --prepared ablation --results runs/ablation
```

La commande enchaîne les trois entraînements et évaluations du kit. On peut cibler un seul run avec `--variant raw`, `--variant clean` ou `--variant dedup`. Le lanceur utilise le premier GPU avec micro-lots de 8 et accumulation pour conserver le lot effectif officiel de 64. Le kit arrondit le budget nominal de 100 M à 3 052 pas, soit 100 007 936 tokens vus par run. Le flux contient un token de contexte supplémentaire, ce qui évite de boucler sur le début au dernier lot. En cas d’interruption, relancer avec le même dossier de résultats pour reprendre depuis le dernier état disponible.

Pour rapatrier uniquement les résultats à consigner, exécuter cette cellule après les runs.

```bash
!zip /kaggle/working/ablation-results.zip runs/ablation/manifest.json runs/ablation/environment.json runs/ablation/*/result.json
```

Télécharger `ablation-results.zip` depuis les sorties Kaggle, l’extraire à la racine du dépôt local, puis importer le journal.

```powershell
uv run --no-sync python -m pipeline.ablation_runs log --results runs/ablation
```

Le BPB provient de `ftb.evaluate` sur les 230 documents, avec un dénominateur de 813 051 octets UTF-8. Le tokenizer ayant appris ses fusions sur le nettoyé, ce choix peut avantager cette variante. La sortie MinHash part du sous-échantillon Wikipédia plafonné à 300 000 articles, donc l’écart nettoyé → dédupliqué porte sur cette sortie du pipeline, sous-échantillonnage compris. Une seule graine est testée. Aucun filtre qualité ni masquage PII dans cette comparaison.

### Variantes qualité et PII sur Kaggle (préparées le 10/11)

Les trois flux (`quality`, `pii`, `quality_pii`) sont construits avec le tokenizer et le protocole de la série de base, sans entraîner de tokenizer : même SHA-256 de tokenizer, même configuration du kit, mêmes quotas 80/12/8 en tokens, 100 007 937 tokens par flux (contexte compris). Les entrées sont les sorties relues et auditées de `quality/final/`, `pii/dedup/` et `pii/quality/`.

```powershell
uv run --no-sync python -m pipeline.ablation_extra        # -> data/processed/ablation-extra/
uv run --no-sync python -m pipeline.ablation_runs bundle --prepared data/processed/ablation-extra --out data/processed/ablation-extra-kaggle.zip
```

| Variante | SHA-256 de `train.bin` |
|---|---|
| Qualité | `f6ad793c15f01cfbcc297e30048061b8619c769bb100e9d9a9b2bc4ffa94c9cf` |
| PII | `5b3b0e9d2c63086425c0f6c76499fc2d2745b2ff8045d32788ccac99dc14d401` |
| Qualité + PII | `62d9a968e184b11d2923f38188bfda3a1e5427369b3820cc9c17cff4870fd033` |

Sur Kaggle (T4, même session que la série de base si possible, Internet activé), importer `ablation-extra-kaggle.zip` puis :

```bash
%cd /kaggle/working
!unzip -o /kaggle/input/CHEMIN/ablation-extra-kaggle.zip
!git clone https://github.com/Meuleur/Piscine.git kit
!git -C kit checkout --detach 3709c85ddaabfcd688d6eea80a5c5ed90605b549
%pip install tokenizers==0.23.3
!python -m pipeline.ablation_runs run --kit kit --prepared ablation --results runs/ablation-extra
!zip /kaggle/working/ablation-extra-results.zip runs/ablation-extra/manifest.json runs/ablation-extra/environment.json runs/ablation-extra/*/result.json
```

`--variant quality`, `pii` ou `quality_pii` cible un seul run. En local, importer les résultats en les comparant au dédupliqué de la série de base :

```powershell
uv run --no-sync python -m pipeline.ablation_runs log --results runs/ablation-extra --reference runs/ablation
```

Le journal refuse la comparaison si le tokenizer, le protocole ou l'environnement GPU diffèrent. Sans `--reference`, la conclusion indique « Comparaison en attente ». Aucun entraînement n'a été lancé pour ces variantes : leur BPB reste à mesurer.
