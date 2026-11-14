# minigpt : bloc 1

## Continuation et pilote conversationnel (11 novembre)

`finetune.py` recharge les poids existants et compare 1 000 pas supplémentaires
avec un taux cosinus de 1e-4 à 1e-5, puis un taux constant de 1e-4. Chaque essai
repart des mêmes poids avec le même tirage (graine 142), batch 32 et quatre threads.
L'optimiseur initial n'étant pas sauvegardé, AdamW est réinitialisé explicitement.
Le meilleur checkpoint, y compris la référence au pas zéro, est conservé.
Résultats : 1,770614 BPB (cosinus), 1,778539 (constant), référence 1,823678.

```powershell
uv run python -m minigpt.finetune --checkpoint checkpoints/moliere_gpt.pt --tokenizer data/processed/bpe_moliere_1024.json --out runs/moliere-continuation
uv run python -m minigpt.dialogue --checkpoint runs/moliere-continuation/cosine/best.pt --reference checkpoints/moliere_gpt.pt --tokenizer data/processed/bpe_moliere_1024.json --out runs/moliere-dialogue
```

Les options de chemins permettent d'utiliser les artefacts d'un autre checkout.
Un dossier de sortie existant est refusé pour ne pas écraser un essai.
`dialogue.py` extrait deux répliques consécutives du seul train du kit, normalise
les espaces et utilise les locuteurs SGANARELLE et DON JUAN.
Les paires qui dépassent 128 tokens sont écartées sans troncature. La loss ignore
la question et le padding (`-100`), mais apprend le premier token de réponse et
la fin de réplique. Aucun dialogue d'entraînement n'est inventé.

Le pilote utilise 400 pas, batch 16, taux 5e-5, graine 2026, sans sélection sur
les questions de test. Les huit questions inédites sont vérifiées absentes du
train original. Les deux exemples déjà essayés par Matisse sont des diagnostics,
pas des tests inédits. `original.json`, `before.json` et `after.json` conservent
toutes les générations brutes et le texte coupé à la première ligne vide (80 tokens,
température 0,7, graine 42 réinitialisée pour chaque question).

Le pilote atteint 1,889077 BPB et 0/8 réponses pertinentes sur les questions
inédites à la graine testée. Le checkpoint du pilote est sauvegardé séparément
dans le dossier de sortie. Le protocole et les exemples figurent dans
[le rapport Molière](../report/moliere_tuning.md).

Mini-GPT codé from scratch, sans boîte noire, entraîné sur le corpus Molière du kit.

| Étape | Fichier prévu | Vérification |
|---|---|---|
| Mini-autograd (`Value` + `backward()`) | `value.py` | gradients comparés à PyTorch |
| Bigramme par comptage | `bigram.py` | BPB de référence sur la validation |
| Tokenizer BPE (train, encode, decode) | `bpe.py` | `decode(encode(x)) == x`, merges calculés à la main ; vocab 1 024 |
| Transformer décodeur | `model.py` | masque causal, attention vs PyTorch, LayerNorm vs `nn.LayerNorm`, surapprentissage d'un batch, BPB par octets ; config CPU 4 couches, 4 têtes, d=128, contexte 128 (~1,07 M param.) |
| Entraînement | `train.py` | courbe de loss, BPB validation, 5 échantillons |

Ce code est écrit à la main : chaque ligne doit pouvoir être expliquée à la soutenance.

## Démo de soutenance multi-tour

`conversation.py` définit le format commun à l'apprentissage et à la génération.
`chat_sft.py` supervise les réponses du corpus dédié et peut garder un rappel du train Molière.
`evaluate_chat.py` rejoue des discussions entières avec les réponses réellement générées.
`web_chat.py` charge les poids sur CPU et sert la page locale. Voir le [rapport de la démo](../report/chat_demo.md) pour les commandes et les résultats.

`combine_checkpoints.py` compare un modèle seul, une moyenne de poids et un ensemble sur les fenêtres de validation habituelles. La commande et le coût des variantes sont dans le [rapport de comparaison](../report/moliere_model_comparison.md).
