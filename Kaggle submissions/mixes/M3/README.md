# M3 : traçabilité du run (Colab T4, 14/11/2026)

**Ce run n'est pas soumissible tel quel** (pas de checkpoint conservé, preuve du lien données/résultat indirecte).

## Ce qui s'est passé

- La session de la CLI Colab a été perdue pendant l'entraînement, mais la VM Colab est allée au bout du run.
- Les fichiers ont été récupérés à la main, depuis le dossier Téléchargements de Matisse.
- Le bon fichier est `evaluation (2).json` (modifié le 14/11 à 22:43, BPB 1,3150705585115026). Il est copié ici sous le nom `evaluation.json`.
- Les autres `evaluation*.json` du dossier sont d'**autres runs** (anciennes ablations du 11/11) : `evaluation (1).json` = 1,3325 (`source-mix-74-18-8`) et `evaluation.json` = 1,3362 (`source-mix-equal`). Ne pas les confondre avec M3.

## Comment on a identifié le run

- Le champ `ckpt` de `evaluation.json` vaut `/content/run-M3/ckpt.pt`, le dossier de sortie du run M3 sur Colab.
- Le `data_meta.json` du run (copié ici) porte `dataset_sha256` = `b771c8aa44f9ebf478fa7c5c4395c071aee410d445505fddf993b5cd217ccb39`, soit le SHA du flux M3 (`data/processed/mixes-m3/M3/`), avec les parts 50/15/10/25.
- Le `tokenizer_sha256` de `evaluation.json` (`b2554a82…`) est celui du tokenizer commun.

## Limites

- `evaluation.json` **ne contient pas le SHA du dataset** : le lien entre ce BPB et le flux M3 passe par le nom du dossier `/content/run-M3` et le `data_meta.json` du même run. La preuve est indirecte.
- `samples.txt` est manquant (non récupéré).
- Pas de checkpoint conservé, pas de journal d'entraînement complet côté CLI (seul `train_log.jsonl` a été récupéré).
- Une seule graine (1337).

## Contrôle de reproductibilité

Une copie de M3 tourne aussi sur Kaggle (même graine, autre GPU). Si elle finit, son BPB sert de contrôle ; c'est la session « mixes-cd » qui l'enregistre dans `LOG.md`. Résultat : à compléter.
