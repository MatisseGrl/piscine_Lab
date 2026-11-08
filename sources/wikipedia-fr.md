# Wikipédia en français

| Champ | Valeur |
|---|---|
| Origine | [Wikimedia sur Hugging Face](https://huggingface.co/datasets/wikimedia/wikipedia/tree/b4c48878f631fc348dd47a4d89c3d1e4b928a0de/20231101.fr), configuration `20231101.fr`, révision `b4c48878f631fc348dd47a4d89c3d1e4b928a0de`. |
| Licence | [CC BY-SA 4.0 et GFDL selon les conditions Wikimedia](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/fr). La fiche du jeu affiche CC BY-SA 3.0 et GFDL. Conserver les URL des articles pour l’attribution et tenir compte des exceptions pour le contenu importé. |
| Volume | 17 fichiers Parquet, 4 614 488 286 octets d’après l’arbre de la révision. Le premier fichier contient 150 862 lignes d’après ses métadonnées. |
| Période couverte | Instantané du 1er novembre 2023. Articles écrits ou modifiés jusqu’à cette date. |
| Date de collecte | 2026-11-08 (échantillon). |
| Type de texte | Articles encyclopédiques en français. |

## Risques

Recouvrement possible avec les textes encyclopédiques de la validation publique par reprises ou extraits, même quand leur publication est plus récente. Des miroirs peuvent aussi dupliquer les articles dans Common Crawl. Recouvrement non mesuré.

## Vérification

Premier Mio du premier fichier Parquet. Lecture à distance du schéma (`id`, `url`, `title`, `text`) et des identifiants, titres et URL de trois articles par requêtes HTTP partielles sur le même fichier.
