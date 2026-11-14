# Dialogues du chat « façon Molière » (démo du bloc 1, hors compétition)

Sources des données de fine-tuning du chat. À citer dans le pptx avec les liens. Ces données ne
servent qu'à la démo : elles n'entrent jamais dans le dataset de la compétition.

## 1. Dialogues maison (utilisés)

| Champ | Valeur |
|---|---|
| Origine | Écrits pour ce projet : `scripts/build_chat_data_v2.py` (modèles de phrases, 7 619 conversations) et `scripts/build_chat_data_v4.py` (40 conversations multi-tours écrites à la main, répétées 8 fois) |
| Licence | Production du projet, aucune source externe |
| Volume | 7 939 conversations, 2,68 Mo de JSON (sha256 `1bddb13f…d970cb31`) |
| Date | 2026-11-11 (v2), 2026-11-14 (v4) |
| Type de texte | Dialogue en deux rôles, civilité du XVIIe (« mon ami », « je vous écoute ») |

**Risques.** Les phrases sont courtes et un peu répétitives (modèles combinatoires). Un recouvrement avec le banc de test est possible : `minigpt.chat_sft` vérifie qu'aucune question DEV/FINAL (normalisée) n'apparaît dans les textes appris, et s'arrête sinon. Résultat de l'audit sur v4 : 0 question trouvée.

## 2. Claire French Dialogue Dataset (en attente, non utilisé à ce jour)

| Champ | Valeur |
|---|---|
| Origine | OpenLLM-France, https://huggingface.co/datasets/OpenLLM-France/Claire-Dialogue-French-0.1 (accès sur demande) |
| Article | Hunter et al., 2023, *The Claire French Dialogue Dataset*, https://arxiv.org/abs/2311.16840 |
| Licence | CC-BY-NC-SA 4.0 : usage non commercial, partage à l'identique. Rien de dérivé ne sera publié. |
| Partie visée | Pièces de théâtre seulement, plafonnées à quelques Mo |

**Conditions d'utilisation décidées le 14/11** : seulement si l'accès HF est obtenu avant le 15/11 à 12 h. Il faut aussi exclure tout texte de Molière, puis faire un audit par séquences de 13 mots contre la validation Molière et contre les 230 documents publics du kit.
