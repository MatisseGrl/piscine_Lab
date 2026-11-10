# Datasheet — corpus français de Feed the Beast

État documentaire au **10 novembre 2026**, préparé par Matisse Garlot pour la piscine I Lab de l’ECE. Organisation selon les rubriques de *Datasheets for Datasets* (Gebru et al., 2018).

**Statut : variantes préparées, dataset final non choisi.** Aucun BPB public mesuré n’est disponible dans l’état de référence de cette fiche. Le choix final attend la comparaison à configuration identique ; aucun gain de qualité prédictive n’est établi par les seuls volumes ou contrôles ci-dessous. Les entraînements Kaggle et le rapport d’ablation sont suivis séparément.

## 1. Motivations et responsabilité

Le corpus sert à entraîner depuis zéro un modèle de langage français dans une compétition pédagogique où l’architecture et le budget sont fixés. L’objectif est de comparer des traitements de données, puis de choisir une variante selon son BPB sur la validation publique du kit. Le BPB divise le coût de prédiction en bits par les **octets UTF-8**, et non par les caractères.

Matisse assure la préparation et la documentation du corpus. Les textes proviennent de tiers ; ils n’ont pas été rédigés sur commande pour ce projet. Aucun financement spécifique, comité d’éthique ou accord individuel des personnes citées n’est documenté dans les pièces locales consultées.

## 2. Composition

### Sources et unités

| Source | Périmètre retenu | Unité documentaire | Période des contenus |
|---|---|---|---|
| Common Crawl | `CC-MAIN-2025-05`, segment `1736703361941.29` ; nettoyage limité aux 10 premières archives WET triées par nom | Texte déjà extrait d’une page web, identifié par le WARC-Record-ID | Captures du 26 janvier 2025 ; dates de publication variables |
| Wikipédia FR | `wikimedia/wikipedia`, configuration `20231101.fr`, révision `b4c48878f631fc348dd47a4d89c3d1e4b928a0de` | Article, identifié par son identifiant Wikipédia | Instantané du 1er novembre 2023 |
| Assemblée nationale | ZIP XML officiel de la 16e législature, chemin `16/vp/` | Section de séance, identifiée par le compte rendu et la section | Juin 2022 à juin 2024 ; export du 28 juin 2024 |

Les sorties textuelles sont des JSONL gzip par source : `id`, `source`, `text`, et `language_score` pour les sorties nettoyées. Le score de langue est une prédiction automatique, pas une annotation humaine. Il n’y a pas de classes cibles ni de graphe de relations entre documents. Les URL et titres des Parquet d’origine ne sont pas des champs systématiquement conservés dans ces sorties ; retrouver l’attribution exige donc aussi les fichiers sources.

Le corpus contient des textes encyclopédiques, du web et des dialogues parlementaires. Il ne constitue pas un échantillon représentatif de tous les francophones. Aucun texte synthétique n’est ajouté dans les variantes documentées. Le corpus Molière téléchargé depuis Wikisource et ses notices sont **exclus** de ces variantes ; le mini-GPT du bloc 1 utilise séparément le corpus du kit.

### Volumes observés et variantes

Les octets désignent le texte encodé en UTF-8, sans enveloppe JSON ni compression. Les volumes des archives téléchargées sont indiqués séparément en section 3.

| Source | Documents lus | Brut exporté après garde-fou | Nettoyé : documents | Nettoyé : octets UTF-8 | Dédupliqué : documents | Dédupliqué : octets UTF-8 |
|---|---:|---:|---:|---:|---:|---:|
| Common Crawl | 328 200 | 328 199 | 13 017 | 91 030 055 | 12 741 | 87 340 486 |
| Wikipédia FR | 2 564 646 | 2 563 979 | 2 507 940 | 7 647 370 763 | 299 873 | 912 560 196 |
| Assemblée nationale | 11 277 | 9 255 | 9 094 | 56 952 466 | 7 705 | 56 773 787 |

Sources des compteurs : `data/interim/clean/stats.json` et `data/interim/dedup/final/stats.json`.

| Variante textuelle préparée | Dossier sous `data/interim/` | Documents | Octets UTF-8 |
|---|---|---:|---:|
| Nettoyé | `clean/` | 2 530 051 | 7 795 353 284 |
| Dédupliqué, avec sous-échantillonnage Wikipédia | `dedup/final/` | 320 319 | 1 056 674 469 |
| Qualité seule après déduplication | `quality/final/` | 320 098 | 1 053 824 598 |
| PII seule après déduplication | `pii/dedup/` | 320 319 | 1 055 854 450 |
| Qualité puis PII après déduplication | `pii/quality/` | 320 098 | 1 053 018 328 |

Le brut d’ablation est dans `clean/raw/` : il s’agit de texte extrait avec garde-fou de validation, pas des fichiers sources intacts. Les dossiers de pilotes et de tests bornés ne sont pas des candidats supplémentaires au dataset final. Le mot `final` dans un chemin désigne la sortie d’une étape, **pas le choix final de compétition**.

### Flux tokenisés déjà préparés

Six flux existent : `raw`, `clean`, `dedup` dans `data/processed/ablation/`, puis `quality`, `pii`, `quality_pii` dans `data/processed/ablation-extra/`. Chaque flux contient 100 007 937 tokens, dont un token de contexte supplémentaire ; le protocole officiel prévoit 100 007 936 tokens vus. Ces nombres décrivent les flux préparés et le budget prévu, pas un entraînement achevé.

Le mélange validé est **80 % Wikipédia FR, 12 % Common Crawl, 8 % Assemblée nationale en tokens cibles**, séparateurs compris. Ce ne sont ni les proportions des documents ni celles des octets des stocks textuels. Le BPE commun de 8 192 entrées a été appris sur 10 000 000 octets du nettoyé, avec ces proportions en octets. Tirages et mélange : graine 42 ; entraînement prévu : graine officielle 1337. Les documents sont tirés sans remise par source ; les quotas peuvent couper au milieu d’un document.

La validation publique du kit reste extérieure aux données d’entraînement : 230 documents, 813 051 octets UTF-8 pour l’évaluation. Il n’existe pas ici de nouveau découpage train/validation/test propre au corpus. Le test caché est géré par l’organisation.

## 3. Collecte

La collecte locale a commencé par les vérifications du 8 novembre 2026 et s’est achevée le 9 novembre après reprises réseau. `pipeline.collect` télécharge les formats existants avec la bibliothèque standard Python ; le projet ne réalise pas un nouveau crawl des sites d’origine et ne réextrait pas leur HTML avec trafilatura.

Le stock téléchargé comprend 900 WET gzip (91 791 596 895 octets), 17 Parquet Wikipédia (4 614 488 286 octets) et un ZIP XML parlementaire (57 553 703 octets, 605 entrées XML). Les tailles HTTP des WET, les SHA-256 LFS des Parquet et le MD5 officiel du ZIP ont été vérifiés selon le suivi local.

Pour tenir le délai et le coût de traitement local, le nettoyage Common Crawl est plafonné à 1 050 000 000 octets compressés : le préfixe de 10 archives entières représente réellement 1 019 886 136 octets. Les 900 archives collectées ne sont donc pas toutes utilisées. Wikipédia et l’Assemblée passent en entier au nettoyage ; Wikipédia est sous-échantillonnée plus tard. Ce préfixe déterministe n’est pas un tirage aléatoire du segment.

Aucune procédure de consentement, notification ou rémunération des auteurs et personnes citées n’est documentée pour ce projet. Le caractère accessible des sources ne prouve pas leur consentement à tous les usages.

## 4. Traitements, contrôles et annotation

### Nettoyage et langue

`pipeline.clean` répare les défauts d’encodage avec ftfy et utilise fastText `lid.176.bin` : le français doit être la première langue prédite avec un score d’au moins **0,80**. Sur les WET, des motifs ciblent menus, cookies et pieds de page. Une ligne normalisée de 25 caractères maximum, répétée au moins trois fois, est retirée aux bords parmi les cinq premières ou dernières lignes non vides.

Les rejets du nettoyé atteignent 96,03 % des documents Common Crawl, 2,21 % de Wikipédia et 19,36 % de l’Assemblée. Ils combinent langue, texte vide et garde-fou de validation : ce ne sont pas des taux de textes de mauvaise qualité. La précision du filtre de langue sur un échantillon annoté manuellement **reste à mesurer**. Le protocole local prévoit un tirage uniforme sans remise, graine 42, annoté `fr`, `autre` ou `mixte`.

### Protection contre le recouvrement de validation

Le garde-fou écarte du brut et du nettoyé les documents partageant une suite de 13 mots avec la validation publique ou la validation Molière ; pour une validation plus courte, il recherche le document entier. La comparaison se fait en minuscules et couvre aussi les raccords créés par la suppression de lignes. Il écarte 1 document Common Crawl, 666 articles Wikipédia et 2 022 sections de l’Assemblée.

Les audits locaux du brut et du nettoyé, puis les `stats.json` des variantes dédupliquées, qualité et PII, indiquent zéro document d’entraînement correspondant, zéro document public signalé et un recouvrement moyen de 0,0 sur les 230 documents publics. Cela ne démontre ni l’absence de paraphrases ou de reprises plus courtes, ni l’absence de tout recouvrement sémantique. Des formules communes peuvent être écartées à tort.

### Déduplication et sous-échantillonnage

La déduplication exacte compare les SHA-256 de textes normalisés en minuscules, NFC et espaces uniformisés. Le premier représentant est conservé dans l’ordre Assemblée, Wikipédia, Common Crawl, puis ordre du fichier. Elle retire 3 815 doublons internes aux sources ; aucun retrait exact entre sources n’est observé.

Après l’exact, 300 000 articles Wikipédia sont tirés sans remise avec la graine 42, retirant séparément 2 205 718 articles. MinHash utilise 96 minima, 16 bandes de six et des suites de cinq mots. Une paire candidate n’est retirée qu’après un Jaccard exact d’au moins **0,97** avec un représentant conservé. Cette étape retire 199 documents : 11 de l’Assemblée, 127 de Wikipédia et 61 de Common Crawl.

Le seuil élevé a été retenu après inspection d’un pilote pour limiter la fusion de textes partageant un gabarit. Des fusions de contenus distincts subsistent, et l’index LSH peut manquer des paires. L’écart nettoyé → dédupliqué inclut le sous-échantillonnage Wikipédia ; il n’isole pas le seul effet de MinHash.

### Qualité

Heuristiques seules : rejet sous 30 % de lettres parmi les caractères hors espaces ; pour Common Crawl uniquement, rejet sous 100 caractères hors espaces ou au-delà de 60 % de lignes répétées à partir de 10 lignes non vides. Le premier motif atteint est compté. Ponctuation et longueur moyenne des mots sont mesurées sans provoquer de rejet.

221 documents Common Crawl sont retirés : 52 trop courts, 165 trop répétitifs, 4 avec trop peu de lettres. Aucun document Wikipédia ou parlementaire n’est retiré. Ce faible nombre ne permet pas de déduire l’effet sur le BPB. Les statistiques et exemples expurgés figurent dans `data/interim/quality/final/stats.json`.

### Données personnelles et masquage

Le masquage repose sur des **regex**, sans Presidio ni reconnaissance des personnes : e-mails, téléphones français, IBAN français à clé modulo 97 valide, URL HTTP(S) ou `www`, IPv4 et IPv6 valides. Les segments deviennent `[EMAIL]`, `[TEL]`, `[IBAN]`, `[URL]` ou `[IP]`. Le reste du texte est conservé.

| Source, sur le dédupliqué avant masquage | E-mails | Téléphones | IBAN | URL | IP |
|---|---:|---:|---:|---:|---:|
| Assemblée nationale | 0 | 0 | 0 | 2 | 0 |
| Wikipédia FR | 30 | 43 | 0 | 9 326 | 1 782 |
| Common Crawl | 4 702 | 6 845 | 2 | 6 252 | 96 |

Ces compteurs de `data/interim/pii/dedup/stats.json` portent sur des **segments détectés**, pas sur des personnes uniques ni sur des données personnelles avérées. Après qualité, les compteurs Common Crawl deviennent 4 607 e-mails, 6 723 téléphones, 2 IBAN, 5 978 URL et 96 IP (`data/interim/pii/quality/stats.json`).

Les noms, adresses postales, informations biographiques et opinions politiques peuvent rester présents, notamment dans les débats et biographies. Une version logicielle telle que `3.10.2.1` peut être masquée à tort comme IP ; certaines IPv6 courtes et des numéros collés à d’autres caractères ne sont pas masqués. Aucune précision ou couverture du détecteur n’est mesurée. **Les variantes PII ne sont pas garanties anonymes.** Les sources brutes et les variantes sans PII restent non masquées.

## 5. Biais, limites et usages

L’usage prévu est l’étude pédagogique du préentraînement français et des traitements de données, avec mesure du BPB dans le protocole du kit. Aucun résultat établi ne justifie encore de préférer une variante. Le tokenizer appris sur le nettoyé peut avantager cette variante dans la comparaison ; une seule graine d’entraînement est prévue.

Le mélange privilégie l’encyclopédie et ajoute des discours institutionnels et des pages web. Il peut sous-représenter les échanges ordinaires, le français oral, les variétés régionales et les pays francophones moins présents dans ces sources. Ces déséquilibres sont des risques liés au choix des sources ; aucune répartition démographique ou géographique n’a été mesurée. Le préfixe WET, le filtre de langue et les heuristiques peuvent exclure des textes courts, mixtes ou atypiques. Le masquage retire aussi des informations techniques utiles.

Des erreurs factuelles, discours discriminatoires, contenus choquants ou opinions partisanes peuvent subsister. Il n’existe ni annotation de toxicité, ni filtre spécifique, ni audit quantitatif de ces contenus. Les dates des sources limitent également l’actualité des connaissances.

Le corpus et les modèles associés ne sont pas validés pour la décision concernant des personnes, le profilage, l’identification, le conseil médical ou juridique, ni pour fournir des faits fiables sans vérification. Le BPB ne mesure ni la sûreté, ni l’équité, ni la véracité des générations. La mémorisation et la restitution de passages ou de données personnelles restent possibles.

## 6. Licences et distribution

Les indications ci-dessous reprennent les fiches locales ; elles ne constituent pas une vérification juridique nouvelle des conditions en vigueur.

| Source | Droits documentés et limites |
|---|---|
| Common Crawl | Conditions d’utilisation Common Crawl ; les droits des pages restent ceux de leurs éditeurs. L’accès aux archives ne donne pas une autorisation générale d’entraîner ou de redistribuer leurs textes. L’éligibilité de chaque contenu n’est pas établie dans les pièces locales. |
| Wikipédia FR | La fiche locale relève CC BY-SA 3.0 et GFDL sur la fiche du jeu, et CC BY-SA 4.0/GFDL dans les conditions Wikimedia. Cette différence et les exceptions des contenus importés restent à clarifier avant redistribution ; l’attribution et les liens vers les articles doivent être reconstituables. |
| Assemblée nationale | Licence Ouverte selon la fiche source : créditer l’Assemblée nationale et indiquer la date de mise à jour. Export documenté : 28 juin 2024. |

Les références d’origine et liens de licences sont dans [Common Crawl](../sources/common-crawl.md), [Wikipédia FR](../sources/wikipedia-fr.md) et [Assemblée nationale](../sources/assemblee-nationale-16.md). **Aucune licence unique du mélange n’est arrêtée.** Le filtrage et le masquage ne suppriment pas les obligations des sources ni les incertitudes sur les droits du web.

Les données sont conservées localement hors Git. Des archives ont été préparées pour un transfert privé vers Kaggle ; leur préparation ne prouve pas une publication. Aucun lien de dataset public Hugging Face ni décision de publication n’est documenté. Les modalités d’accès, de redistribution et de retrait public restent donc à définir avant une éventuelle diffusion.

### Empreintes des flux candidats

Ces SHA-256 identifient les `train.bin` préparés, **pas un dataset final sélectionné**. Les empreintes par source et la filiation des traitements sont conservées dans les `stats.json` et les deux `manifest.json` des dossiers `data/processed/ablation/` et `data/processed/ablation-extra/`.

| Flux | SHA-256 |
|---|---|
| Brut | `151ca028be94476949cc43504323741076a017e63ca307dbc2dbc2240962d8f0` |
| Nettoyé | `71c5a146a04676041e37b64d2d7e295a88f64915a304b22e523302c6872a4002` |
| Dédupliqué | `56ee10c62f6d9c2a6c2d48a060c2eae3850819f46c62ecd782a2c0a7ee7faaad` |
| Qualité | `f6ad793c15f01cfbcc297e30048061b8619c769bb100e9d9a9b2bc4ffa94c9cf` |
| PII | `5b3b0e9d2c63086425c0f6c76499fc2d2745b2ff8045d32788ccac99dc14d401` |
| Qualité puis PII | `62d9a968e184b11d2923f38188bfda3a1e5427369b3820cc9c17cff4870fd033` |

Tokenizer commun : `b2554a8221a55c19b4008f5b605b1b6e84b6a7f84058507c15aba34eca3b2379`.

## 7. Maintenance et éléments à compléter

Matisse maintient cette fiche et le pipeline dans le dépôt du projet. Aucun calendrier de mise à jour, durée de conservation, adresse de contact dédiée ou mécanisme formalisé de demande de retrait n’est documenté. Les sources sont figées pour cette comparaison ; toute nouvelle collecte ou modification de traitement devra être identifiée par de nouvelles statistiques et empreintes.

Les commandes existantes et paramètres sont décrits dans [pipeline/README.md](../pipeline/README.md) : collecte, nettoyage plafonné, déduplication, qualité, PII, puis préparation des flux de base et supplémentaires. La reconstruction actuelle passe par plusieurs commandes ; une commande globale allant de la collecte à toutes les variantes n’est pas documentée. Les graines et révisions sont consignées ; les sorties existantes ne doivent pas être écrasées lors d’une régénération.

Pour clôturer la datasheet du **dataset final**, il reste à renseigner la variante choisie avec ses BPB réels et son empreinte, la précision annotée du filtre français, les décisions de droits et de distribution, puis les modalités de maintenance et de retrait si une publication est décidée. Le détail des comparaisons appartient à [report/ablation.md](ablation.md).
