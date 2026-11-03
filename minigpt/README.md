# minigpt : bloc 1

Mini-GPT codé from scratch, sans boîte noire, entraîné sur le corpus Molière du kit.

| Étape | Fichier prévu | Vérification |
|---|---|---|
| Mini-autograd (`Value` + `backward()`) | `value.py` | gradients comparés à PyTorch |
| Bigramme par comptage | `bigram.py` | BPB de référence sur la validation |
| Tokenizer BPE (train, encode, decode) | `bpe.py` | `decode(encode(x)) == x` |
| Transformer décodeur | `model.py` | masque causal : aucun token ne voit le futur |
| Entraînement | `train.py` | courbe de loss, BPB validation, 5 échantillons |

Ce code est écrit à la main : chaque ligne doit pouvoir être expliquée à la soutenance.
