# sources

Sources de la collecte du bloc 2 :

- [Common Crawl (WET)](common-crawl.md)
- [Wikipédia FR](wikipedia-fr.md)
- [Débats de la 16e législature](assemblee-nationale-16.md)

Sources de la démo de chat et du bloc 1 (hors compétition) :

- [Molière du kit (Projet Gutenberg) et dialogues du projet](chat-demo.md)
- [Wikisource : théâtre de Molière](wikisource-moliere.md) (collecté, non utilisé pour l'entraînement)
- [OpenAssistant/oasst1](oasst1.md) (examiné, écarté)

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
