# Comparaison des modèles Molière du 12 novembre

La référence est le checkpoint cosinus à 1,770614 BPB. Les comparaisons utilisent le même tokenizer BPE de 1 024 tokens, les mêmes fenêtres de 128 tokens et les mêmes octets de validation du kit. Les poids et journaux restent dans le worktree local.

| Méthode | BPB Molière | Coût à l'inférence |
|---|---:|---|
| Continuation cosinus | 1,770614 | Un mini-GPT |
| Moyenne des poids du cosinus, du taux constant et du pas 400 de la reprise sur le kit | **1,766015** | Un mini-GPT |
| Moyenne uniforme des probabilités de six checkpoints | 1,748069 | Six mini-GPT |
| Même ensemble avec comptage de motifs du train | 1,704266 | Six mini-GPT et des tables de fréquences |

La moyenne des poids donne `runs/moliere-combination-three/average.pt`. La mesure de l'ensemble et des fréquences est dans `runs/moliere-combination-six/measures.json`, avec les empreintes des checkpoints et corpus. Le modèle de fréquences utilise au plus les cinq tokens précédents, dans la fenêtre actuelle. Son poids augmente quand le préfixe apparaît plusieurs fois dans le train. L'ensemble et le modèle hybride sont des mesures exploratoires pour le bloc 1. Le modèle de démo continue de générer avec ses propres poids. Le seuil demandé de 1,500 BPB reste à atteindre.

```powershell
uv run --frozen python -m minigpt.combine_checkpoints --checkpoints ../moliere-continuation-20261111/cosine/best.pt ../moliere-continuation-20261111/constant/best.pt runs/night-20261111-231345/kit/step-400.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --validation ../../kit/Piscine/corpus/moliere_val.txt --save-average --out runs/compare-three-repro
uv run --frozen python -m minigpt.combine_checkpoints --checkpoints ../moliere-continuation-20261111/cosine/best.pt ../moliere-continuation-20261111/constant/best.pt ../../checkpoints/moliere_gpt.pt runs/night-20261111-231345/kit/step-400.pt runs/chat-main-v2-r30/step-4000.pt runs/night-20261111-231345/dropout/step-400.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --validation ../../kit/Piscine/corpus/moliere_val.txt --ngram-train ../../kit/Piscine/corpus/moliere_train.txt --out runs/compare-six-repro
```

## Chat

L'essai de nuit a terminé au pas 1 600 à 1,826807 BPB. Son dernier checkpoint obtient 1/8 sur les réparations de développement. Plusieurs erreurs apparaissent aussi quand le modèle reçoit la question seule. Cela a motivé l'ajout de paraphrases originales et de mauvaises répliques variées. Le nouveau corpus contient 4 730 conversations et son SHA-256 est `c70f7f54462b466d0e487f9910f65788f37808fa0d5da3a7139cc5d227a8cf20`. L'audit ne retrouve aucune relance réservée et aucune séquence de 13 mots de la validation. La mauvaise réplique reste une entrée et la loss supervise uniquement la correction.

```powershell
uv run --frozen python -m scripts.build_chat_paraphrases --base runs/chat-data-repair/train.json --out runs/chat-data-paraphrases
uv run --frozen python -m scripts.audit_chat_data --data runs/chat-data-paraphrases/train.json --tokenizer ../../data/processed/bpe_moliere_1024.json --corpus ../../kit/Piscine/corpus --out runs/chat-data-paraphrases/audit.json
uv run --frozen python -m minigpt.chat_sft --checkpoint runs/night-20261111-231345/chat/step-1600.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --data runs/chat-data-paraphrases/train.json --corpus ../../kit/Piscine/corpus --out runs/chat-paraphrases-a --steps 900 --every 150 --lr 0.00015 --replay 0.15 --repair-bench --threads 3
```

## Supplément de fréquences

Un seul mini-GPT avec les fréquences du train obtient **1,713132 BPB**. L'ensemble et les fréquences du train plus cinq pièces Wikisource obtiennent **1,696002 BPB**, avec une fraction maximale de 0,6, choisie sur la validation parmi 0,4, 0,5, 0,6 et 0,7. L'essai utilise donc des données supplémentaires pour les tables de fréquences. La validation est identique à celle du kit. Le contrôle de 13 mots n'a trouvé aucun recouvrement entre le supplément et la validation. La provenance du supplément est décrite dans le [rapport de reprise](moliere_restart.md).

Le réglage choisi séparément sur les cinq pièces Wikisource, avant leur ajout aux tables, donne 1,714392 BPB sur le kit. Il fait moins bien que le réglage initial à 1,704266 sur le kit. Un masque exploratoire des paires incompatibles avec le BPE a ramené l'hybride sans supplément à 1,702521 BPB. Cette variante ajoute une contrainte de décodage et n'est pas celle retenue.

```powershell
uv run --frozen python -m minigpt.combine_checkpoints --checkpoints ../moliere-continuation-20261111/cosine/best.pt ../moliere-continuation-20261111/constant/best.pt ../../checkpoints/moliere_gpt.pt runs/night-20261111-231345/kit/step-400.pt runs/chat-main-v2-r30/step-4000.pt runs/night-20261111-231345/dropout/step-400.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --validation ../../kit/Piscine/corpus/moliere_val.txt --ngram-train ../../kit/Piscine/corpus/moliere_train.txt --ngram-extra runs/moliere-extra/train_extra.txt --ngram-fraction 0.6 --out runs/compare-extra-repro
```

## Résultat des relances inédites

Le pas 900 termine à 1,875898 BPB et réussit 3/8 sur les réparations de développement. Le pas 450 et la moyenne des poids des pas 300 et 450 atteignent 5/8. La moyenne est retenue avant ouverture du test inédit parce qu'elle conserve davantage d'échanges ordinaires sur le développement. Son BPB est 1,856629.

| Modèle | Réparations inédites /8 | BPB Molière |
|---|---:|---:|
| Démo actuelle | 0 | 1,854847 |
| SFT de réparation de nuit, pas 1 600 | 1 | 1,826807 |
| Moyenne des pas 300 et 450 avec paraphrases | 1 | 1,856629 |

Le nouveau modèle se présente correctement après une relance. Il échoue notamment sur la promenade, le repas rapide et la recherche du cahier. Le score de développement surestime donc le gain sur les relances inédites. Les réponses sont annotées à la lecture et l'historique comporte une mauvaise réplique imposée. La démo garde son checkpoint de la PR #23. Voir les [générations et annotations](moliere_repair_results.json).

```powershell
uv run --frozen python -m minigpt.combine_checkpoints --checkpoints runs/chat-paraphrases-a/step-300.pt runs/chat-paraphrases-a/step-450.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --validation ../../kit/Piscine/corpus/moliere_val.txt --save-average --out runs/chat-average-repro
uv run --frozen python -m minigpt.evaluate_chat --repair --split final --checkpoints runs/chat-main-v2-r30/step-1000.pt runs/night-20261111-231345/chat/step-1600.pt runs/chat-average-repro/average.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --out runs/chat-repairs-final-repro
```

Les 138 tests passent. Les mesures BPB avec et sans les cinq pièces ont été reproduites par le nouveau point d'entrée. Les [mesures numériques et empreintes](moliere_combination_results.json) sont archivées.
