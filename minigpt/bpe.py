"""Tokenizer BPE (Byte Pair Encoding) au niveau octet, codé from scratch.

Idée : on part des 256 octets (vocab de base, tout texte est encodable). On répète :
trouver la paire de tokens voisins la plus fréquente du corpus, la remplacer partout par
un nouveau token. Chaque merge ajoute 1 au vocab, jusqu'à vocab_size.

Pré-découpage : le texte est d'abord coupé en « mots » (lettres avec l'espace qui les
précède, ponctuation, blancs). Les merges ne traversent jamais deux mots : les tokens
restent des morceaux de mots, et l'entraînement va vite car on ne compte chaque mot
distinct qu'une fois (pondéré par sa fréquence).

Usage : uv run python -m minigpt.bpe [vocab_size]
"""

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

from minigpt.bigram import CORPUS, load_utf8

# Un morceau = espace optionnel + lettres/chiffres, OU espace optionnel + ponctuation,
# OU une suite de blancs. Les trois cas couvrent tous les caractères : la concaténation
# des morceaux redonne exactement le texte (indispensable pour decode(encode(x)) == x).
# \w de Python est Unicode : « é », « ç », « œ » comptent comme des lettres.
SPLIT_PATTERN = re.compile(r" ?\w+| ?[^\w\s]+|\s+")


def merge_pair(ids: list[int], pair: tuple[int, int], new_id: int) -> list[int]:
    """Remplace chaque occurrence de pair dans ids par new_id (de gauche à droite)."""
    out = []
    i = 0
    while i < len(ids):
        # Paire trouvée : on écrit le nouveau token et on saute les deux anciens.
        if i + 1 < len(ids) and ids[i] == pair[0] and ids[i + 1] == pair[1]:
            out.append(new_id)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out


class BPETokenizer:
    """BPE octet : merges[(a, b)] = id du token qui fusionne a et b, vocab[id] = ses octets."""

    def __init__(self):
        """Tokenizer vide : seulement les 256 octets, aucun merge."""
        # L'ordre d'insertion des merges = l'ordre d'apprentissage = la priorité à l'encodage.
        self.merges: dict[tuple[int, int], int] = {}
        self.vocab: dict[int, bytes] = {i: bytes([i]) for i in range(256)}
        # Cache mot -> ids : les mots se répètent énormément, on ne les encode qu'une fois.
        self._cache: dict[str, list[int]] = {}

    def train(self, text: str, vocab_size: int, verbose: bool = False) -> "BPETokenizer":
        """Apprend vocab_size - 256 merges sur text. Égalité de fréquence : la paire vue en premier gagne."""
        assert vocab_size >= 256, "le vocab contient au moins les 256 octets"
        # Mots distincts -> fréquence (Counter garde l'ordre de première apparition).
        word_freq = Counter(SPLIT_PATTERN.findall(text))
        # Chaque mot devient la liste de ses octets UTF-8, avec sa fréquence.
        words = [(list(w.encode("utf-8")), f) for w, f in word_freq.items()]

        for new_id in range(256, vocab_size):
            # 1. Compter les paires voisines, pondérées par la fréquence du mot.
            pair_counts: dict[tuple[int, int], int] = {}
            for ids, freq in words:
                for pair in zip(ids, ids[1:]):
                    pair_counts[pair] = pair_counts.get(pair, 0) + freq
            if not pair_counts:
                break  # plus aucune paire : chaque mot est déjà un seul token
            # 2. Paire la plus fréquente (max garde la première en cas d'égalité).
            best = max(pair_counts, key=pair_counts.get)
            # 3. La fusionner partout et l'enregistrer.
            words = [(merge_pair(ids, best, new_id), f) for ids, f in words]
            self.merges[best] = new_id
            self.vocab[new_id] = self.vocab[best[0]] + self.vocab[best[1]]
            if verbose and (new_id - 255) % 100 == 0:
                print(f"merge {new_id - 255}/{vocab_size - 256} : {self.vocab[new_id]!r} ({pair_counts[best]} fois)")
        self._cache.clear()
        return self

    def _encode_word(self, word: str) -> list[int]:
        """Encode un seul mot : applique les merges dans l'ordre où ils ont été appris."""
        if word in self._cache:
            return self._cache[word]
        ids = list(word.encode("utf-8"))
        while len(ids) >= 2:
            # Parmi les paires présentes, celle apprise le plus tôt (plus petit id) passe d'abord,
            # pour reproduire exactement l'ordre de l'entraînement.
            pair = min(zip(ids, ids[1:]), key=lambda p: self.merges.get(p, float("inf")))
            if pair not in self.merges:
                break  # plus aucune paire fusionnable
            ids = merge_pair(ids, pair, self.merges[pair])
        self._cache[word] = ids
        return ids

    def encode(self, text: str) -> list[int]:
        """Texte -> liste d'ids : pré-découpage en mots, puis BPE mot par mot."""
        ids = []
        for word in SPLIT_PATTERN.findall(text):
            ids.extend(self._encode_word(word))
        return ids

    def decode(self, ids: list[int]) -> str:
        """Ids -> texte : on recolle les octets de chaque token, puis on décode l'UTF-8."""
        data = b"".join(self.vocab[i] for i in ids)
        # errors="replace" : une suite d'ids arbitraire (ex. générée) peut couper un caractère.
        return data.decode("utf-8", errors="replace")

    def save(self, path: Path) -> None:
        """Sauve les merges dans l'ordre (le vocab se reconstruit à partir d'eux)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"merges": [list(p) for p in self.merges]}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "BPETokenizer":
        """Recharge un tokenizer sauvé par save()."""
        tok = cls()
        for a, b in json.loads(Path(path).read_text(encoding="utf-8"))["merges"]:
            new_id = 256 + len(tok.merges)
            tok.merges[(a, b)] = new_id
            tok.vocab[new_id] = tok.vocab[a] + tok.vocab[b]
        return tok


def main() -> None:
    """Entraîne le BPE sur moliere_train.txt, affiche la compression et des exemples de tokens."""
    # Console Windows en cp1252 : on force l'UTF-8 pour afficher les accents des tokens.
    sys.stdout.reconfigure(encoding="utf-8")
    vocab_size = int(sys.argv[1]) if len(sys.argv) > 1 else 1024
    train = load_utf8(CORPUS / "moliere_train.txt").decode("utf-8")
    val = load_utf8(CORPUS / "moliere_val.txt").decode("utf-8")

    start = time.perf_counter()
    tok = BPETokenizer().train(train, vocab_size, verbose=True)
    print(f"entraînement : {time.perf_counter() - start:.1f} s, vocab = {len(tok.vocab)}")

    # Taux de compression = octets UTF-8 / tokens (1,0 = aucun gain par rapport aux octets).
    for name, text in [("train", train), ("val", val)]:
        ids = tok.encode(text)
        assert tok.decode(ids) == text, f"aller-retour cassé sur {name}"
        n_bytes = len(text.encode("utf-8"))
        print(f"{name} : {n_bytes:,} octets -> {len(ids):,} tokens, {n_bytes / len(ids):.3f} octets/token")

    print("10 premiers merges :", [tok.vocab[i].decode("utf-8", "replace") for i in range(256, 266)])
    print("10 derniers merges :", [tok.vocab[i].decode("utf-8", "replace") for i in range(len(tok.vocab) - 10, len(tok.vocab))])
    longest = sorted(tok.vocab.values(), key=len, reverse=True)[:10]
    print("10 plus longs     :", [t.decode("utf-8", "replace") for t in longest])

    out = Path(f"data/processed/bpe_moliere_{vocab_size}.json")
    tok.save(out)
    print(f"merges sauvés dans {out}")


if __name__ == "__main__":
    main()
