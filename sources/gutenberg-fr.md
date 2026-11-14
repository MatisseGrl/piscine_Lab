# Project Gutenberg FR

| Champ | Valeur |
|---|---|
| Origine | Project Gutenberg, catalogue officiel `pg_catalog.csv` (https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv), textes `https://www.gutenberg.org/cache/epub/<id>/pg<id>.txt`. Livres de type `Text` dont la langue est exactement `fr` (4 207). Manifeste (IDs, titres, auteurs, SHA-256 par livre) : `data/raw/gutenberg/manifest.json`, SHA-256 `e5f1182652f7ec209f45cd13149b31d13de54a09764ea1de986b6f8694d498b2` |
| Licence | Domaine public aux États-Unis ; Project Gutenberg License (https://www.gutenberg.org/policy/license.html). Les en-têtes et pieds de page de la licence sont retirés (la marque « Project Gutenberg » n'apparaît plus dans le texte). Statut hors États-Unis : à compléter. |
| Volume | Avant : 4 191 livres téléchargés (21 introuvables), 1 797 870 743 octets UTF-8 bruts. Après retrait des en-têtes : 4 170 livres, 1 673 099 317 octets. **Final : 4 094 livres, 1 635 329 505 octets UTF-8.** Tokens : non mesurés avec le tokenizer 8 192 ; estimation ~3,5 octets par token, soit ~470 M tokens (à confirmer). |
| Période couverte | Principalement XVIIIe–début XXe siècle (domaine public). Dates exactes : à compléter. |
| Date de collecte | 2026-11-14 |
| Type de texte | Littéraire : romans, théâtre, poésie, essais, récits de voyage. Un document = un livre. |

## Risques
- **Orthographe ancienne et vers** : conservées. Le test est en français moderne, l'apport est donc surtout lexical et stylistique.
- **Molière / validation** : la validation du kit contient *Le Misanthrope*, *L'Avare*, *Le Sicilien*. Exclus avant téléchargement : 4 eBooks du kit (40086, 43535, 50173, 57270), 11 livres dont l'auteur ou le titre contient « Molière », 1 titre de pièce de la validation.
- **Granularité** : le filtre 13 mots écarte le livre entier, jamais un extrait. 59 livres (31,2 Mo) sont partis pour recouvrement, ce qui peut retirer des livres citant simplement une pièce.
- Mélange de langues dans un même livre (latin, anglais) possible : la langue est évaluée sur le livre entier.
- Pas de PII appliquée (non demandée). Noms de personnes présents, texte du domaine public.
- Résidus possibles : tables des matières ou notes non reconnues par les heuristiques, numéros de page, scories d'OCR.

## Traitement
1. Catalogue puis exclusions (ci-dessus), collecte à 4 fils avec délai, agent identifiable, cache local reprenable.
2. Retrait de l'en-tête et du pied de page (`*** START OF` / `*** END OF`, sinon rejet `no_markers`), des notes du transcripteur, des illustrations et des tables des matières (heuristique par blocs).
3. ftfy (79 livres modifiés), fastText `lid.176.bin` français ≥ 0,80 : 12 livres rejetés (`low_confidence`, 3,9 Mo).
4. Contamination 13 mots contre les 230 documents publics et la validation Molière : 59 rejets. Contrôle final : zéro recouvrement sur la sortie.
5. Dédup exacte sur textes normalisés (minuscules, NFC, espaces) : 2 retraits ; MinHash 0,97 (mêmes fonctions que `pipeline.dedup`) : 3 retraits.
6. Filtre qualité actuel (`low_letters`) : 0 rejet.

Commande : `uv run python -m pipeline.gutenberg`. Sortie : `data/interim/gutenberg/gutenberg_fr.jsonl.gz` (SHA-256 `b63c6472f20825cac131a679ddc262a2bac344dbd6ef4650985517b9cc9c7cf0`) et `stats.json` (copie : `sources/gutenberg-fr.stats.json`). Octets comptés en UTF-8, graine 42.
