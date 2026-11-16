# OpenAssistant/oasst1 (examiné, écarté)

| Champ | Valeur |
|---|---|
| Origine | [OpenAssistant/oasst1 sur Hugging Face](https://huggingface.co/datasets/OpenAssistant/oasst1), révision `fdf72ae0827c1cda404aff25b6603abec9e3399b` |
| Licence | Apache 2.0 |
| Volume | 2 474 messages français dans le train ; 37 candidats après filtre (racine autonome, réponse humaine, rang 0 ou absent, question ≤ 50 tokens, réponse ≤ 80 tokens) |
| Période couverte | non relevée |
| Date de collecte | inspection locale du 11/11/2026 (candidats sous `runs/oasst-inspection/`, hors git) |
| Type de texte | dialogue assistant / utilisateur |

## Usage
**Non utilisé dans l'entraînement.** Examiné pour la démo de chat (jamais pour la compétition), puis écarté après lecture complète des candidats.

## Risques
Réponses hors sujet, datées ou factuellement douteuses (exemples : réponse « Ça tourne ! » à une demande Angular, météo sans contexte temporel). Trop peu de candidats pertinents pour justifier le mélange.

## Traitement
Filtre ci-dessus, inspection manuelle, rejet. Détail dans `report/chat_demo.md`.
