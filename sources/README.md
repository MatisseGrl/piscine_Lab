# sources

Sources de la collecte du bloc 2 :

- [Common Crawl (WET)](common-crawl.md)
- [Wikipédia FR](wikipedia-fr.md)
- [Débats de la 16e législature](assemblee-nationale-16.md)

Une fiche par source, nommée `<source>.md` (ex. `common-crawl.md`, `wikipedia-fr.md`). Modèle à copier :

```markdown
# <Nom de la source>

| Champ | Valeur |
|---|---|
| Origine | URL, éditeur, comment on l'obtient |
| Licence | nom exact + lien ; usage autorisé pour l'entraînement ? |
| Volume | documents, octets, tokens (avant / après pipeline) |
| Période couverte | dates des textes |
| Date de collecte | AAAA-MM-JJ |
| Type de texte | encyclopédique, littéraire, presse, dialogue, web... |

## Risques
Données personnelles, contenu toxique, biais, doublons avec d'autres sources, recouvrement possible avec la validation.

## Traitement
Étapes du pipeline appliquées et ce qu'elles ont retiré.
```
