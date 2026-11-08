# minigpt : bloc 1

Mini-GPT codé from scratch, sans boîte noire, entraîné sur le corpus Molière du kit.

| Étape | Fichier prévu | Vérification |
|---|---|---|
| Mini-autograd (`Value` + `backward()`) | `value.py` | gradients comparés à PyTorch |
| Bigramme par comptage | `bigram.py` | BPB de référence sur la validation |
| Tokenizer BPE (train, encode, decode) | `bpe.py` | `decode(encode(x)) == x`, merges calculés à la main ; vocab 1 024 |
| Transformer décodeur | `model.py` | masque causal, attention vs PyTorch, LayerNorm vs `nn.LayerNorm`, surapprentissage d'un batch, BPB par octets ; config CPU 4 couches, 4 têtes, d=128, contexte 128 (~1,07 M param.) |
| Entraînement | `train.py` | courbe de loss, BPB validation, 5 échantillons |

Ce code est écrit à la main : chaque ligne doit pouvoir être expliquée à la soutenance.
