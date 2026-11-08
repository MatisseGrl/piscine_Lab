# Common Crawl — CC-MAIN-2025-05

| Champ | Valeur |
|---|---|
| Origine | Common Crawl Foundation, [index WET officiel](https://data.commoncrawl.org/crawl-data/CC-MAIN-2025-05/wet.paths.gz), segment `1736703361941.29`. Le WET contient le texte extrait des pages et leurs métadonnées WARC. |
| Licence | [Conditions d’utilisation de Common Crawl](https://commoncrawl.org/terms-of-use). Les droits sur les pages dépendent de leurs éditeurs. L’accès à l’archive ne donne pas une autorisation générale d’entraîner ou de redistribuer les textes. |
| Volume | 900 fichiers WET gzip dans l’index. Premier fichier : 102 325 106 octets annoncés. Plusieurs dizaines de Gio estimés pour le segment, volume total et nombre de documents non mesurés. |
| Période couverte | Captures du 26 janvier 2025 d’après les noms de fichiers et les enregistrements contrôlés. Les dates de publication des pages varient. |
| Date de collecte | 2026-11-08 (échantillon). |
| Type de texte | Web multilingue. |

## Risques

Droits variables, données personnelles, textes toxiques, doublons et recouvrement possible avec la validation publique du kit par reprise de textes de presse, d’encyclopédie ou de littérature. Le recouvrement reste à mesurer avant entraînement.

## Vérification

Premier Mio compressé du premier WET. Lecture de l’en-tête `warcinfo` et de deux enregistrements `conversion` complets. Les fichiers restent au format source.
