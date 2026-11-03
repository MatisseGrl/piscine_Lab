# Wikisource : théâtre de Molière

| Champ | Valeur |
|---|---|
| Origine | fr.wikisource.org, page [Auteur:Molière](https://fr.wikisource.org/wiki/Auteur:Moli%C3%A8re), section « Pièces de théâtre » ; récupéré via l'API MediaWiki par `scripts/fetch_moliere.py` |
| Licence | Textes du domaine public (Molière, mort en 1673 ; Charles Louandre, mort en 1886). Wikisource diffuse ses pages sous CC BY-SA 4.0 : attribution « Wikisource » conservée, liste des pages et révisions dans `manifest.json` |
| Volume | 33 pièces, voir `data/raw/moliere/manifest.json` (octets et sha256 par fichier) |
| Période couverte | Pièces de 1645 à 1673 ; édition Louandre (Charpentier, 1910) pour la plupart, sinon la meilleure édition disponible sur Wikisource |
| Date de collecte | 2026-11-03 |
| Type de texte | Littéraire : théâtre en vers et en prose, XVIIᵉ siècle |

## Usage
**Non utilisé pour l'entraînement** (décision du 3/11) : le bloc 1 s'entraîne uniquement sur les données du kit (`kit/Piscine/corpus/moliere_train.txt`) et mesure le BPB sur `moliere_val.txt`. Ce corpus est gardé pour référence seulement.

**Recouvrement avec le kit** : le kit a 28 pièces (éd. Chasles 1888, Gutenberg), ce corpus en a 33, dont les 3 pièces de validation du kit (Le Misanthrope, L'Avare, Le Sicilien). Ne jamais le mélanger au train du bloc 1, sinon le BPB de validation est faussé. Pièces en plus ici : Comtesse d'Escarbagnas, Fourberies de Scapin, Bourgeois gentilhomme, Femmes savantes, Malade imaginaire, Psyché.

## Deux sorties
- `data/raw/moliere/` : le texte des pièces seul (personnages, actes, répliques).
- `data/raw/moliere_notices/` : les notices de l'éditeur Louandre (1910) et les textes de tiers (Neuf-Villenaine). Ce n'est pas du Molière ; non utilisé pour l'entraînement.

## Risques
- **Édition non homogène** : quelques pièces viennent d'une autre édition que Louandre 1910 (orthographe, ponctuation et didascalies différentes).
- **Psyché** est coécrite avec Corneille et Quinault : ce n'est pas du Molière pur.
- **Pastorale comique** est un fragment (quelques ko).
- **Orthographe ancienne** par endroits (« feroit ») : c'est normal pour le style, mais à garder en tête pour la compétition, dont le test set est en français moderne.
- Pas de données personnelles (textes du XVIIᵉ siècle).
- Le corpus du kit vient de Gutenberg (éd. Chasles 1888), pas de Wikisource : mêmes pièces en grande partie, mais édition, ponctuation et mise en page différentes.

## Traitement
Le HTML rendu est converti en texte brut UTF-8 : une ligne par vers, une ligne vide avant chaque réplique et chaque titre (acte, scène). Supprimés : navigation, numéros de page, appels et textes de notes, demi-vers recopiés en caché pour l'alignement des vers partagés, sommaire en tête de page.
